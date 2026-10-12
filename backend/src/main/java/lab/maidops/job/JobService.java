package lab.maidops.job;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;

import lab.maidops.api.ApiException;
import lab.maidops.api.CursorCodec;
import lab.maidops.api.PageResponse;
import lab.maidops.domain.JobStatus;
import lab.maidops.project.ProjectRepository;
import lab.maidops.project.RegisteredTaskEntity;
import lab.maidops.project.RegisteredTaskRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class JobService {
    private static final String KEY_PATTERN = "^[A-Za-z0-9._:-]{8,128}$";

    private final JobRepository jobs;
    private final JobEventRepository events;
    private final IdempotencyKeyRepository keys;
    private final ProjectRepository projects;
    private final RegisteredTaskRepository tasks;
    private final IdAllocator ids;
    private final JdbcTemplate jdbcTemplate;
    private final int eventLimit;

    public JobService(
            JobRepository jobs,
            JobEventRepository events,
            IdempotencyKeyRepository keys,
            ProjectRepository projects,
            RegisteredTaskRepository tasks,
            IdAllocator ids,
            JdbcTemplate jdbcTemplate,
            @Value("${maidops.event-limit:500}") int eventLimit) {
        this.jobs = jobs;
        this.events = events;
        this.keys = keys;
        this.projects = projects;
        this.tasks = tasks;
        this.ids = ids;
        this.jdbcTemplate = jdbcTemplate;
        this.eventLimit = eventLimit;
    }

    @Transactional
    public JobResponse create(String projectId, String taskId, String idempotencyKey) {
        RegisteredTaskEntity task = requireTask(projectId, taskId);
        String hash = hash(projectId, taskId);
        IdempotencyKeyEntity reserved = reserve(idempotencyKey, hash);
        if (reserved != null && reserved.getJobId() != null) {
            return get(reserved.getJobId());
        }
        Instant now = Instant.now();
        JobEntity job = jobs.save(JobEntity.queued(ids.nextJobId(), task.getProjectId(), task.getId(), now));
        append(job, "QUEUED. 등록된 명령이 있으면 워커가 가져갑니다. 아직 실행 결과는 없습니다.", now);
        if (reserved != null) {
            reserved.setJobId(job.getId());
        }
        return JobResponse.from(job);
    }

    @Transactional(readOnly = true)
    public PageResponse<JobResponse> list(String cursor, Integer limit) {
        int pageSize = pageSize(limit);
        CursorCodec.Cursor position = CursorCodec.decode(cursor);
        List<JobEntity> rows = position == null
                ? jobs.firstPage(pageSize + 1)
                : jobs.pageAfter(position.createdAt(), position.id(), pageSize + 1);
        return page(rows, pageSize);
    }

    @Transactional(readOnly = true)
    public JobResponse get(String jobId) {
        return JobResponse.from(requireJob(jobId));
    }

    @Transactional(readOnly = true)
    public PageResponse<JobEventResponse> events(String jobId, Integer after) {
        requireJob(jobId);
        List<JobEventEntity> rows = after == null
                ? displayOrder(jobId)
                : events.findByJob_IdAndSequenceNoGreaterThanOrderBySequenceNoAsc(jobId, after);
        List<JobEventResponse> items = rows.stream().map(JobEventResponse::from).toList();
        return new PageResponse<>(items, null);
    }

    @Transactional
    public JobResponse cancel(String jobId) {
        JobEntity job = lock(jobId);
        if (job.getStatus().terminal()) {
            throw new ApiException(
                    409,
                    "STATE",
                    "이미 종료된 작업은 취소할 수 없습니다: " + job.getId() + " " + job.getStatus().name(),
                    "/jobs");
        }
        Instant now = Instant.now();
        job.setCancelRequestedAt(now);
        append(job, "CANCEL requested", now);
        if (job.getStatus() == JobStatus.QUEUED) {
            job.setStatus(JobStatus.CANCELLED);
            job.setFinishedAt(now);
            append(job, "RESULT CANCELLED", now);
            return JobResponse.from(job);
        }
        job.setStatus(JobStatus.CANCEL_REQUESTED);
        return JobResponse.from(job);
    }

    /**
     * 이후 워커가 RUNNING 작업에만 종료 결과를 반영할 때 쓸 규칙이다.
     * HTTP로 노출하지 않으며, 이 단계에서는 스케줄러도 호출하지 않는다.
     * QUEUED와 종료 상태는 바꾸지 않는다.
     */
    @Transactional
    public JobResponse applyTerminalResultIfRunning(String jobId, JobStatus result) {
        if (result != JobStatus.SUCCEEDED && result != JobStatus.FAILED) {
            throw new ApiException(400, "VALIDATION", "종료 결과는 SUCCEEDED 또는 FAILED만 가능합니다.", "");
        }
        JobEntity job = lock(jobId);
        if (job.getStatus() != JobStatus.RUNNING) {
            return JobResponse.from(job);
        }
        Instant now = Instant.now();
        job.setStatus(result);
        job.setFinishedAt(now);
        String line = result == JobStatus.SUCCEEDED ? "RESULT PASS" : "RESULT FAIL";
        append(job, line, now);
        return JobResponse.from(job);
    }

    /**
     * 경합 테스트가 미래의 워커 claim을 대신한다. HTTP로 노출하지 않는다.
     */
    @Transactional
    public JobResponse markRunning(String jobId) {
        JobEntity job = lock(jobId);
        if (job.getStatus() != JobStatus.QUEUED) {
            throw new ApiException(409, "STATE", "QUEUED 작업만 RUNNING으로 바꿀 수 있습니다.", "");
        }
        Instant now = Instant.now();
        job.setStatus(JobStatus.RUNNING);
        job.setStartedAt(now);
        append(job, "RUNNING", now);
        return JobResponse.from(job);
    }

    private IdempotencyKeyEntity reserve(String idempotencyKey, String hash) {
        if (idempotencyKey == null) {
            return null;
        }
        if (!idempotencyKey.matches(KEY_PATTERN)) {
            throw new ApiException(
                    400,
                    "VALIDATION",
                    "Idempotency-Key 형식이 올바르지 않습니다.",
                    "8자 이상의 영문, 숫자, ., _, :, -");
        }
        jdbcTemplate.update(
                "insert into idempotency_keys (key_text, request_hash, created_at) values (?, ?, ?) on conflict (key_text) do nothing",
                idempotencyKey,
                hash,
                java.sql.Timestamp.from(Instant.now()));
        IdempotencyKeyEntity key = keys.lockByKey(idempotencyKey)
                .orElseThrow(() -> new ApiException(500, "INTERNAL", "요청 키를 저장하지 못했습니다.", ""));
        if (!key.getRequestHash().equals(hash)) {
            throw new ApiException(
                    409,
                    "CONFLICT",
                    "같은 Idempotency-Key로 다른 작업 요청이 이미 있습니다.",
                    idempotencyKey);
        }
        return key;
    }

    private RegisteredTaskEntity requireTask(String projectId, String taskId) {
        if (!projects.existsById(projectId)) {
            throw new ApiException(404, "NOT_FOUND", "프로젝트를 찾지 못했습니다: " + projectId, "/project list");
        }
        RegisteredTaskEntity task = tasks.findById(taskId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "등록된 작업을 찾지 못했습니다: " + taskId, ""));
        if (!task.getProjectId().equals(projectId)) {
            throw new ApiException(400, "VALIDATION", "작업이 선택한 프로젝트에 속하지 않습니다.", "");
        }
        return task;
    }

    private JobEntity requireJob(String jobId) {
        return jobs.findById(jobId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "작업을 찾지 못했습니다: " + jobId, "/jobs"));
    }

    public JobEntity lock(String jobId) {
        return jobs.findLockedById(jobId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "작업을 찾지 못했습니다: " + jobId, "/jobs"));
    }

    public void append(JobEntity job, String text, Instant createdAt) {
        append(job, "SYSTEM", text, createdAt);
    }

    public void append(JobEntity job, String stream, String text, Instant createdAt) {
        int sequence = events.maxSequence(job.getId()) + 1;
        String stored = text.length() > 2000 ? text.substring(0, 2000) : text;
        events.save(JobEventEntity.create(job, sequence, stream, stored, createdAt));
        events.flush();
        trim(job);
    }

    private void trim(JobEntity job) {
        List<JobEventEntity> all = new ArrayList<>(events.findByJob_IdOrderBySequenceNoAsc(job.getId()));
        if (all.size() <= eventLimit) {
            return;
        }
        job.setOutputTruncated(true);
        int keep = Math.max(1, eventLimit - 1);
        List<JobEventEntity> drop = all.subList(0, all.size() - keep);
        events.deleteAll(drop);
        events.flush();
        int sequence = events.maxSequence(job.getId()) + 1;
        events.save(JobEventEntity.create(
                job,
                sequence,
                "SYSTEM",
                "[출력 잘림] 최근 " + eventLimit + "줄만 표시합니다.",
                Instant.now()));
    }

    private List<JobEventEntity> displayOrder(String jobId) {
        List<JobEventEntity> rows = new ArrayList<>(events.findByJob_IdOrderBySequenceNoAsc(jobId));
        JobEventEntity marker = null;
        List<JobEventEntity> rest = new ArrayList<>();
        for (JobEventEntity row : rows) {
            if (row.getText().startsWith("[출력 잘림]")) {
                marker = row;
            } else {
                rest.add(row);
            }
        }
        if (marker == null) {
            return rows;
        }
        List<JobEventEntity> ordered = new ArrayList<>();
        ordered.add(marker);
        ordered.addAll(rest);
        return ordered;
    }

    private PageResponse<JobResponse> page(List<JobEntity> rows, int pageSize) {
        boolean more = rows.size() > pageSize;
        List<JobEntity> page = more ? rows.subList(0, pageSize) : rows;
        String next = null;
        if (more && !page.isEmpty()) {
            JobEntity last = page.get(page.size() - 1);
            next = CursorCodec.encode(last.getCreatedAt(), last.getId());
        }
        return new PageResponse<>(page.stream().map(JobResponse::from).toList(), next);
    }

    private int pageSize(Integer limit) {
        int resolved = limit == null ? 50 : limit;
        if (resolved < 1 || resolved > 100) {
            throw new ApiException(400, "VALIDATION", "limit은 1 이상 100 이하여야 합니다.", "50");
        }
        return resolved;
    }

    private static String hash(String projectId, String taskId) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest((projectId + "\n" + taskId).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException(exception);
        }
    }
}
