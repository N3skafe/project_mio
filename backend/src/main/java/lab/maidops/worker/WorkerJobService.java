package lab.maidops.worker;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.List;
import java.util.Optional;

import jakarta.persistence.EntityManager;
import lab.maidops.api.ApiException;
import lab.maidops.domain.JobStatus;
import lab.maidops.lab.ModelDraftService;
import lab.maidops.job.JobEntity;
import lab.maidops.job.JobEventRepository;
import lab.maidops.job.JobRepository;
import lab.maidops.job.JobResponse;
import lab.maidops.job.JobService;
import lab.maidops.project.RegisteredTaskEntity;
import lab.maidops.project.RegisteredTaskRepository;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class WorkerJobService {
    private final JdbcTemplate jdbcTemplate;
    private final EntityManager entityManager;
    private final JobRepository jobs;
    private final JobService jobService;
    private final JobEventRepository events;
    private final RegisteredTaskRepository tasks;
    private final RegisteredCommandResolver commands;
    private final ModelDraftService modelDrafts;
    private final String workspaceRoot;
    private final int leaseSeconds;

    public WorkerJobService(
            JdbcTemplate jdbcTemplate,
            EntityManager entityManager,
            JobRepository jobs,
            JobService jobService,
            JobEventRepository events,
            RegisteredTaskRepository tasks,
            RegisteredCommandResolver commands,
            ModelDraftService modelDrafts,
            @Value("${maidops.workspace-root:}") String workspaceRoot,
            @Value("${maidops.lease-seconds:15}") int leaseSeconds) {
        this.jdbcTemplate = jdbcTemplate;
        this.entityManager = entityManager;
        this.jobs = jobs;
        this.jobService = jobService;
        this.events = events;
        this.tasks = tasks;
        this.commands = commands;
        this.modelDrafts = modelDrafts;
        this.workspaceRoot = workspaceRoot;
        this.leaseSeconds = leaseSeconds;
    }

    @Transactional
    public void heartbeat(String workerId) {
        requireWorkerId(workerId);
        Instant now = Instant.now();
        jdbcTemplate.update(
                """
                insert into worker_sessions (worker_id, last_heartbeat_at) values (?, ?)
                on conflict (worker_id) do update set last_heartbeat_at = excluded.last_heartbeat_at
                """,
                workerId,
                Timestamp.from(now));
    }

    @Transactional
    public Optional<ClaimedJob> claim(String workerId) {
        requireWorkerId(workerId);
        heartbeat(workerId);
        Instant now = Instant.now();
        String jobId = jdbcTemplate.query(
                """
                update jobs
                set status = 'RUNNING',
                    worker_id = ?,
                    started_at = coalesce(started_at, ?),
                    lease_expires_at = ?
                where id = (
                    select j.id
                    from jobs j
                    inner join registered_tasks t on t.id = j.task_id
                    where j.status = 'QUEUED' and t.argv_json is not null
                    order by j.created_at, j.id
                    for update skip locked
                    limit 1
                )
                returning id
                """,
                ps -> {
                    ps.setString(1, workerId);
                    ps.setTimestamp(2, Timestamp.from(now));
                    ps.setTimestamp(3, Timestamp.from(now.plusSeconds(leaseSeconds)));
                },
                rs -> rs.next() ? rs.getString(1) : null);
        if (jobId == null) {
            return Optional.empty();
        }
        entityManager.flush();
        entityManager.clear();
        JobEntity job = jobs.findById(jobId).orElseThrow();
        jobService.append(job, "RUNNING. owner=" + workerId, now);
        RegisteredTaskEntity task = tasks.findById(job.getTaskId()).orElseThrow();
        RegisteredCommandResolver.Resolved resolved = commands.resolve(
                workspaceRoot == null || workspaceRoot.isBlank() ? null : java.nio.file.Path.of(workspaceRoot),
                task);
        if (!resolved.accepted()) {
            failWithoutRerun(job, "등록 명령을 실행하지 못했습니다. " + resolved.reason(), null, false);
            return Optional.empty();
        }
        return Optional.of(new ClaimedJob(
                job.getId(),
                resolved.argv(),
                resolved.workingDirectory(),
                resolved.timeoutSeconds()));
    }

    @Transactional
    public void heartbeatJob(String workerId, String jobId) {
        requireWorkerId(workerId);
        heartbeat(workerId);
        Instant lease = Instant.now().plusSeconds(leaseSeconds);
        int updated = jdbcTemplate.update(
                """
                update jobs
                set lease_expires_at = ?
                where id = ? and worker_id = ? and status in ('RUNNING', 'CANCEL_REQUESTED')
                """,
                Timestamp.from(lease),
                jobId,
                workerId);
        if (updated == 0) {
            throw new ApiException(409, "STATE", "이 작업의 소유 워커가 아니거나 이미 종료되었습니다.", jobId);
        }
    }

    @Transactional
    public void appendOutput(String workerId, String jobId, List<OutputLine> lines) {
        JobEntity job = owned(workerId, jobId);
        if (job.getStatus().terminal()) {
            return;
        }
        Instant now = Instant.now();
        for (OutputLine line : lines) {
            if (line.text() == null || line.text().isBlank()) {
                continue;
            }
            String stream = normalizeStream(line.stream());
            jobService.append(job, stream, line.text().replace("\r", ""), now);
            if (job.isOutputTruncated()) {
                break;
            }
        }
    }

    @Transactional
    public JobResponse finish(String workerId, String jobId, FinishRequest request) {
        JobEntity job = owned(workerId, jobId);
        if (job.getStatus().terminal()) {
            return JobResponse.from(job);
        }
        if (!request.processExited()) {
            jobService.append(job, "프로세스 종료를 확인하지 못했습니다. CANCELLED로 바꾸지 않습니다.", Instant.now());
            return JobResponse.from(job);
        }
        Instant now = Instant.now();
        job.setExitCode(request.exitCode());
        if (job.getStatus() == JobStatus.CANCEL_REQUESTED) {
            job.setStatus(JobStatus.CANCELLED);
            job.setFinishedAt(now);
            job.setCancelConfirmedAt(now);
            jobService.append(job, "RESULT CANCELLED exit_code=" + request.exitCode(), now);
            return JobResponse.from(job);
        }
        if (request.timedOut() || request.exitCode() == null || request.exitCode() != 0) {
            failWithoutRerun(job, resultLine(request), request.exitCode(), request.timedOut());
            return JobResponse.from(job);
        }
        job.setStatus(JobStatus.SUCCEEDED);
        job.setFinishedAt(now);
        jobService.append(job, "RESULT PASS exit_code=0", now);
        return JobResponse.from(job);
    }

    @Transactional
    public int expireLeases() {
        List<JobEntity> expired = jobs.findExpired(Instant.now());
        int count = 0;
        for (JobEntity candidate : expired) {
            JobEntity job = jobService.lock(candidate.getId());
            if (job.getStatus().terminal()) {
                continue;
            }
            if (job.getLeaseExpiresAt() == null || !job.getLeaseExpiresAt().isBefore(Instant.now())) {
                continue;
            }
            if (job.getStatus() != JobStatus.RUNNING && job.getStatus() != JobStatus.CANCEL_REQUESTED) {
                continue;
            }
            failWithoutRerun(job, "WORKER_LOST. 임대가 만료되었습니다. 자동 재실행하지 않습니다.", job.getExitCode(), false);
            count++;
        }
        return count;
    }

    private void failWithoutRerun(JobEntity job, String line, Integer exitCode, boolean timedOut) {
        Instant now = Instant.now();
        job.setStatus(JobStatus.FAILED);
        job.setFinishedAt(now);
        job.setExitCode(exitCode);
        String text = timedOut ? "TIMEOUT. " + line : line;
        jobService.append(job, text, now);
        if (!text.startsWith("RESULT FAIL")) {
            jobService.append(job, "RESULT FAIL exit_code=" + exitCode, now);
        }
        modelDrafts.recordFailure(job.getId(), job.getProjectId(), failureText(job, exitCode, timedOut), now);
    }

    private String failureText(JobEntity job, Integer exitCode, boolean timedOut) {
        StringBuilder builder = new StringBuilder();
        builder.append("exit_code=").append(exitCode).append('\n');
        builder.append("timed_out=").append(timedOut).append('\n');
        events.findByJob_IdOrderBySequenceNoAsc(job.getId()).forEach(event -> {
            if (builder.length() < 7000) {
                builder.append(event.getText()).append('\n');
            }
        });
        return builder.toString();
    }

    private static String resultLine(FinishRequest request) {
        if (request.timedOut()) {
            return "RESULT FAIL exit_code=" + request.exitCode() + " timeout";
        }
        return "RESULT FAIL exit_code=" + request.exitCode();
    }

    private JobEntity owned(String workerId, String jobId) {
        requireWorkerId(workerId);
        JobEntity job = jobService.lock(jobId);
        if (job.getWorkerId() == null || !job.getWorkerId().equals(workerId)) {
            throw new ApiException(409, "STATE", "이 작업의 소유 워커가 아닙니다.", jobId);
        }
        if (job.getStatus() != JobStatus.RUNNING && job.getStatus() != JobStatus.CANCEL_REQUESTED && !job.getStatus().terminal()) {
            throw new ApiException(409, "STATE", "워커가 기록할 수 있는 상태가 아닙니다.", job.getStatus().name());
        }
        return job;
    }

    private static void requireWorkerId(String workerId) {
        if (workerId == null || !workerId.matches("^[A-Za-z0-9._:-]{4,64}$")) {
            throw new ApiException(400, "VALIDATION", "X-Worker-Id 형식이 올바르지 않습니다.", "worker-1");
        }
    }

    private static String normalizeStream(String stream) {
        if ("STDOUT".equals(stream) || "STDERR".equals(stream) || "SYSTEM".equals(stream)) {
            return stream;
        }
        throw new ApiException(400, "VALIDATION", "stream은 STDOUT, STDERR, SYSTEM 중 하나여야 합니다.", "STDOUT");
    }

    public record ClaimedJob(String jobId, List<String> argv, String workingDirectory, int timeoutSeconds) {
    }

    public record OutputLine(String stream, String text) {
    }

    public record FinishRequest(Integer exitCode, boolean processExited, boolean timedOut) {
    }
}
