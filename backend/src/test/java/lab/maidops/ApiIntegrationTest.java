package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

import static org.hamcrest.Matchers.nullValue;

import com.jayway.jsonpath.JsonPath;
import lab.maidops.api.ApiException;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.JobStatus;
import lab.maidops.domain.LabelSource;
import lab.maidops.domain.ReviewStatus;
import lab.maidops.errorcase.ErrorCaseEntity;
import lab.maidops.errorcase.ErrorCaseRepository;
import lab.maidops.errorcase.LabelRevisionEntity;
import lab.maidops.job.JobResponse;
import lab.maidops.job.JobService;
import lab.maidops.worker.WorkerJobService;
import lab.maidops.worker.WorkerJobService.FinishRequest;
import lab.maidops.worker.WorkerJobService.OutputLine;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

@SpringBootTest(properties = "maidops.event-limit=3")
@AutoConfigureMockMvc
class ApiIntegrationTest extends PostgresTestSupport {
    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JobService jobs;

    @Autowired
    private ErrorCaseRepository errorCases;

    @Autowired
    private WorkerJobService workerJobs;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @DynamicPropertySource
    static void workspace(DynamicPropertyRegistry registry) {
        Path root = Path.of("..", "fixtures", "trusted-projects").toAbsolutePath().normalize();
        registry.add("maidops.workspace-root", root::toString);
    }

    @Test
    void healthReportsDatabaseUpAndWorkerDisconnected() throws Exception {
        jdbcTemplate.update("delete from worker_sessions");
        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("UP"))
                .andExpect(jsonPath("$.database").value("UP"))
                .andExpect(jsonPath("$.worker").value("NOT_CONNECTED"))
                .andExpect(jsonPath("$.authentication").value("NONE"));
    }

    @Test
    void createStaysQueuedAndDoesNotPretendSuccess() throws Exception {
        String body = createJob("idem-queued-0001", "demo-api", "api-db-check");
        assertThat(body).contains("\"status\":\"QUEUED\"");
        assertThat(body).doesNotContain("SUCCEEDED").doesNotContain("RESULT PASS").doesNotContain("RESULT FAIL");
        String id = JsonPath.read(body, "$.id");
        String events = events(id);
        assertThat(events).contains("QUEUED");
        assertThat(events).doesNotContain("RESULT PASS").doesNotContain("RESULT FAIL");
        assertThat(JsonPath.<String>read(body, "$.started_at")).isNull();
    }

    @Test
    void repeatedIdempotencyKeyReturnsTheSameJob() throws Exception {
        String first = createJob("idem-same-0001", "demo-web", "web-health");
        String second = createJob("idem-same-0001", "demo-web", "web-health");
        assertThat(JsonPath.<String>read(first, "$.id")).isEqualTo(JsonPath.<String>read(second, "$.id"));
    }

    @Test
    void sameIdempotencyKeyWithAnotherTaskConflicts() throws Exception {
        createJob("idem-conflict-01", "demo-api", "api-db-check");
        mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", "idem-conflict-01")
                        .content("{\"project_id\":\"demo-web\",\"task_id\":\"web-health\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("CONFLICT"));
    }

    @Test
    void invalidInputAndUnknownProjectAreRejected() throws Exception {
        mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"\",\"task_id\":\"api-db-check\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
        mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", "idem-missing-01")
                        .content("{\"project_id\":\"missing\",\"task_id\":\"api-db-check\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"));
        mockMvc.perform(get("/api/v1/jobs").param("limit", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
        mockMvc.perform(get("/api/v1/search").param("q", " "))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
    }

    @Test
    void cancelQueuedJobStaysCancelledWhenCompletionArrivesLate() throws Exception {
        String id = JsonPath.read(createJob("idem-cancel-0001", "demo-api", "api-db-check"), "$.id");
        String cancelled = mockMvc.perform(post("/api/v1/jobs/" + id + "/cancel"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(cancelled).contains("\"status\":\"CANCELLED\"");
        JobResponse afterLateSuccess = jobs.applyTerminalResultIfRunning(id, JobStatus.SUCCEEDED);
        assertThat(afterLateSuccess.status()).isEqualTo(JobStatus.CANCELLED);
        String events = events(id);
        assertThat(events).contains("CANCEL requested").contains("RESULT CANCELLED");
        assertThat(events).doesNotContain("RESULT PASS").doesNotContain("RESULT FAIL");
        mockMvc.perform(post("/api/v1/jobs/" + id + "/cancel"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STATE"));
    }

    @Test
    void runningCompletionAndCancelDoNotOverwriteEachOther() throws Exception {
        String id = JsonPath.read(createJob("idem-race-00001", "demo-web", "web-health"), "$.id");
        jobs.markRunning(id);
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);
        AtomicReference<Throwable> cancelError = new AtomicReference<>();
        pool.submit(() -> runExclusive(ready, start, cancelError, () -> jobs.cancel(id)));
        pool.submit(() -> runExclusive(ready, start, new AtomicReference<>(), () -> jobs.applyTerminalResultIfRunning(id, JobStatus.SUCCEEDED)));
        assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
        start.countDown();
        pool.shutdown();
        assertThat(pool.awaitTermination(10, TimeUnit.SECONDS)).isTrue();
        JobResponse result = jobs.get(id);
        String eventBody = events(id);
        assertThat(result.status()).isIn(JobStatus.SUCCEEDED, JobStatus.CANCEL_REQUESTED);
        if (result.status() == JobStatus.CANCEL_REQUESTED) {
            assertThat(eventBody).doesNotContain("RESULT PASS");
            assertThat(cancelError.get()).isNull();
        } else {
            assertThat(eventBody).contains("RESULT PASS");
            assertThat(cancelError.get()).isInstanceOf(ApiException.class);
            mockMvc.perform(post("/api/v1/jobs/" + id + "/cancel")).andExpect(status().isConflict());
        }
    }

    @Test
    void thereIsNoHttpEndpointThatMarksSuccess() throws Exception {
        mockMvc.perform(post("/api/v1/jobs/job-00000001/complete"))
                .andExpect(status().isNotFound());
    }

    @Test
    void jobListIsPagedWithoutDuplicates() throws Exception {
        Set<String> created = new HashSet<>();
        for (int index = 0; index < 3; index++) {
            String body = createJob("idem-page-" + index + "-01", "demo-api", "api-db-check");
            created.add(JsonPath.read(body, "$.id"));
        }
        Set<String> seen = new HashSet<>();
        String cursor = null;
        for (int page = 0; page < 5; page++) {
            var request = get("/api/v1/jobs").param("limit", "2");
            if (cursor != null) {
                request.param("cursor", cursor);
            }
            MvcResult result = mockMvc.perform(request).andExpect(status().isOk()).andReturn();
            String body = result.getResponse().getContentAsString(StandardCharsets.UTF_8);
            seen.addAll(JsonPath.read(body, "$.items[*].id"));
            cursor = JsonPath.read(body, "$.next_cursor");
            if (cursor == null) {
                break;
            }
        }
        assertThat(seen).containsAll(created);
        mockMvc.perform(get("/api/v1/jobs").param("cursor", "not-a-cursor"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
    }

    @Test
    void reviewAndResolutionFollowTheStoredState() throws Exception {
        String jobId = JsonPath.read(createJob("idem-review-0001", "demo-api", "api-db-check"), "$.id");
        ErrorCaseEntity errorCase = new ErrorCaseEntity();
        errorCase.setId("case-manual-0001");
        errorCase.setJobId(jobId);
        errorCase.setProjectId("demo-api");
        errorCase.setRawText("stored text for review, not a live test result");
        errorCase.setDraftLabel(ErrorLabel.DB_CONNECTION);
        errorCase.setDraftSource(LabelSource.FIXTURE);
        errorCase.setCurrentLabel(ErrorLabel.DB_CONNECTION);
        errorCase.setReviewStatus(ReviewStatus.DRAFT);
        errorCase.setOrigin(DataOrigin.SESSION);
        errorCase.setCreatedAt(Instant.parse("2026-10-06T00:00:00Z"));
        errorCase.addRevision(LabelRevisionEntity.create(
                ErrorLabel.DB_CONNECTION,
                ReviewStatus.DRAFT,
                LabelSource.FIXTURE,
                "테스트가 직접 저장한 사례입니다.",
                Instant.parse("2026-10-06T00:00:00Z")));
        errorCases.saveAndFlush(errorCase);

        mockMvc.perform(get("/api/v1/error-cases/case-manual-0001"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.review_status").value("DRAFT"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()));
        mockMvc.perform(post("/api/v1/error-cases/case-manual-0001/resolutions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cause\":\"원인\",\"method\":\"방법\"}"))
                .andExpect(status().isConflict());
        mockMvc.perform(post("/api/v1/error-cases/case-manual-0001/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"REVISE\",\"label\":\"DB_CONNECTION\"}"))
                .andExpect(status().isBadRequest());
        mockMvc.perform(post("/api/v1/error-cases/case-manual-0001/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"REVISE\",\"label\":\"AUTH_PERMISSION\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.review_status").value("REVISED"))
                .andExpect(jsonPath("$.draft_label").value("DB_CONNECTION"))
                .andExpect(jsonPath("$.current_label").value("AUTH_PERMISSION"))
                .andExpect(jsonPath("$.confirmed_label").value("AUTH_PERMISSION"));
        mockMvc.perform(post("/api/v1/error-cases/case-manual-0001/resolutions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cause\":\"권한 토큰이 없었습니다\",\"method\":\"토큰 발급을 확인합니다\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.origin").value("SESSION"));
        mockMvc.perform(get("/api/v1/resolutions").param("q", "토큰"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].origin").value("SESSION"));
        mockMvc.perform(get("/api/v1/search").param("q", "없는키워드zzz"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items").isEmpty());
    }

    @Test
    void onlyOneWorkerClaimsAQueuedCommand() throws Exception {
        String id = JsonPath.read(createJob("idem-claim-00001", "trusted-sample", "sample-pass"), "$.id");
        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);
        AtomicReference<String> first = new AtomicReference<>();
        AtomicReference<String> second = new AtomicReference<>();
        pool.submit(() -> runExclusive(ready, start, new AtomicReference<>(), () -> first.set(claimId("worker-a"))));
        pool.submit(() -> runExclusive(ready, start, new AtomicReference<>(), () -> second.set(claimId("worker-b"))));
        assertThat(ready.await(5, TimeUnit.SECONDS)).isTrue();
        start.countDown();
        pool.shutdown();
        assertThat(pool.awaitTermination(10, TimeUnit.SECONDS)).isTrue();
        assertThat(List.of(first.get(), second.get()).stream().filter(id::equals).count()).isEqualTo(1);
        workerJobs.finish("worker-a".equals(ownerOf(first, second, id)) ? "worker-a" : "worker-b", id,
                new FinishRequest(0, true, false));
    }

    @Test
    void recordedExitCodeAndLogBecomeTheFailure() throws Exception {
        String id = JsonPath.read(createJob("idem-fail-000001", "trusted-sample", "sample-fail"), "$.id");
        assertThat(claimId("worker-fail")).isEqualTo(id);
        workerJobs.appendOutput("worker-fail", id, java.util.List.of(new OutputLine("STDERR", "boom")));
        JobResponse finished = workerJobs.finish("worker-fail", id, new FinishRequest(2, true, false));
        assertThat(finished.status()).isEqualTo(JobStatus.FAILED);
        assertThat(finished.exitCode()).isEqualTo(2);
        String boomId = caseIdContaining("boom");
        mockMvc.perform(get("/api/v1/error-cases/" + boomId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_label").value("OTHER"))
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.rule_version").value("rules-1"))
                .andExpect(jsonPath("$.matched_keyword").value(nullValue()))
                .andExpect(jsonPath("$.review_status").value("DRAFT"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.raw_text").value(org.hamcrest.Matchers.containsString("exit_code=2")))
                .andExpect(jsonPath("$.raw_text").value(org.hamcrest.Matchers.containsString("boom")))
                .andExpect(jsonPath("$.score").doesNotExist());
        JobResponse again = workerJobs.finish("worker-fail", id, new FinishRequest(0, true, false));
        assertThat(again.status()).isEqualTo(JobStatus.FAILED);
        assertThat(again.exitCode()).isEqualTo(2);
    }

    @Test
    void cancelRequestIsNotSuccessUntilTheProcessExits() throws Exception {
        String id = JsonPath.read(createJob("idem-slow-000001", "trusted-sample", "sample-slow"), "$.id");
        assertThat(claimId("worker-slow")).isEqualTo(id);
        String requested = mockMvc.perform(post("/api/v1/jobs/" + id + "/cancel"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(requested).contains("\"status\":\"CANCEL_REQUESTED\"");
        JobResponse hiddenSuccess = workerJobs.finish("worker-slow", id, new FinishRequest(0, false, false));
        assertThat(hiddenSuccess.status()).isEqualTo(JobStatus.CANCEL_REQUESTED);
        JobResponse confirmed = workerJobs.finish("worker-slow", id, new FinishRequest(0, true, false));
        assertThat(confirmed.status()).isEqualTo(JobStatus.CANCELLED);
        assertThat(events(id)).doesNotContain("RESULT PASS");
    }

    @Test
    void expiredLeaseIsNotRequeued() throws Exception {
        String id = JsonPath.read(createJob("idem-lease-00001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-lease")).isEqualTo(id);
        jdbcTemplate.update(
                "update jobs set lease_expires_at = ? where id = ?",
                Timestamp.from(Instant.parse("2020-01-01T00:00:00Z")),
                id);
        assertThat(workerJobs.expireLeases()).isGreaterThanOrEqualTo(1);
        JobResponse expired = jobs.get(id);
        assertThat(expired.status()).isEqualTo(JobStatus.FAILED);
        assertThat(events(id)).contains("자동 재실행하지 않습니다");
        assertThat(claimId("worker-lease-2")).isNotEqualTo(id);
    }

    @Test
    void unreviewedRuleDraftIsNotAConfirmedLabel() throws Exception {
        String failed = JsonPath.read(createJob("idem-rule-db-0001", "trusted-sample", "sample-fail"), "$.id");
        assertThat(claimId("worker-rule")).isEqualTo(failed);
        workerJobs.appendOutput("worker-rule", failed, List.of(new OutputLine(
                "STDERR",
                "org.postgresql.util.PSQLException: Connection to localhost:5432 refused")));
        workerJobs.finish("worker-rule", failed, new FinishRequest(2, true, false));
        String draftId = caseIdContaining("5432 refused");
        mockMvc.perform(get("/api/v1/error-cases/" + draftId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_label").value("DB_CONNECTION"))
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.rule_version").value("rules-1"))
                .andExpect(jsonPath("$.matched_keyword").value("postgresql"))
                .andExpect(jsonPath("$.review_status").value("DRAFT"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.revisions[0].source").value("RULE_BASED"))
                .andExpect(jsonPath("$.score").doesNotExist());
        assertThat(confirmedBody()).doesNotContain(draftId);

        mockMvc.perform(post("/api/v1/error-cases/" + draftId + "/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"DEFER\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.review_status").value("DEFERRED"))
                .andExpect(jsonPath("$.draft_label").value("DB_CONNECTION"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.revisions[1].source").value("USER"));
        assertThat(confirmedBody()).doesNotContain(draftId);

        String second = JsonPath.read(createJob("idem-rule-input-01", "trusted-sample", "sample-fail"), "$.id");
        assertThat(claimId("worker-rule-2")).isEqualTo(second);
        workerJobs.appendOutput("worker-rule-2", second, List.of(new OutputLine(
                "STDERR",
                "Validation failed: required field email is missing")));
        workerJobs.finish("worker-rule-2", second, new FinishRequest(2, true, false));
        String inputId = caseIdContaining("required field email");
        mockMvc.perform(post("/api/v1/error-cases/" + inputId + "/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"REVISE\",\"label\":\"OTHER\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_label").value("INPUT_VALIDATION"))
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.current_label").value("OTHER"))
                .andExpect(jsonPath("$.confirmed_label").value("OTHER"))
                .andExpect(jsonPath("$.review_status").value("REVISED"))
                .andExpect(jsonPath("$.revisions[0].source").value("RULE_BASED"))
                .andExpect(jsonPath("$.revisions[1].source").value("USER"));
        String confirmed = confirmedBody();
        assertThat(confirmed).contains(inputId).doesNotContain(draftId);
        mockMvc.perform(post("/api/v1/error-cases/" + inputId + "/resolutions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cause\":\"phase4-unique-cause\",\"method\":\"필수 필드를 채웁니다\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.origin").value("SESSION"));
        mockMvc.perform(get("/api/v1/search").param("q", "phase4-unique-cause"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].kind").value("RESOLUTION"))
                .andExpect(jsonPath("$.items[0].excerpt").value(org.hamcrest.Matchers.containsString("phase4-unique-cause")));
        String errorHit = mockMvc.perform(get("/api/v1/search").param("q", "required field email"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(errorHit).contains("ERROR_CASE").contains(inputId).contains("RULE_BASED");
    }

    @Test
    void outputLimitExceededIsNotSuccessWhenExitCodeIsZero() throws Exception {
        String id = JsonPath.read(createJob("idem-limit-00001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-limit")).isEqualTo(id);
        workerJobs.appendOutput("worker-limit", id, List.of(new OutputLine("STDOUT", "partial")));
        JobResponse finished = workerJobs.finish(
                "worker-limit",
                id,
                new FinishRequest(0, true, false, true, "OUTPUT_LIMIT_EXCEEDED"));
        assertThat(finished.status()).isEqualTo(JobStatus.FAILED);
        assertThat(finished.exitCode()).isZero();
        assertThat(finished.outputTruncated()).isTrue();
        assertThat(finished.terminationReason()).isEqualTo("OUTPUT_LIMIT_EXCEEDED");
        String body = events(id);
        assertThat(body).contains("OUTPUT_LIMIT_EXCEEDED").doesNotContain("RESULT PASS");
    }

    @Test
    void retainedLogTrimStaysSuccessful() throws Exception {
        String id = JsonPath.read(createJob("idem-trim-000001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-trim")).isEqualTo(id);
        workerJobs.appendOutput("worker-trim", id, List.of(new OutputLine("STDOUT", "one"), new OutputLine("STDOUT", "two")));
        JobResponse finished = workerJobs.finish("worker-trim", id, new FinishRequest(0, true, false));
        assertThat(finished.status()).isEqualTo(JobStatus.SUCCEEDED);
        assertThat(finished.terminationReason()).isEqualTo("COMPLETED");
        assertThat(finished.outputTruncated()).isTrue();
        String body = events(id);
        assertThat(body).contains("[출력 잘림]").doesNotContain("OUTPUT_LIMIT_EXCEEDED").contains("RESULT PASS");
    }

    @Test
    void supervisionFailureIsNotSuccess() throws Exception {
        String id = JsonPath.read(createJob("idem-sup-0000001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-sup")).isEqualTo(id);
        JobResponse finished = workerJobs.finish(
                "worker-sup",
                id,
                new FinishRequest(0, true, false, false, "SUPERVISION_FAILED"));
        assertThat(finished.status()).isEqualTo(JobStatus.FAILED);
        assertThat(finished.terminationReason()).isEqualTo("SUPERVISION_FAILED");
        assertThat(events(id)).doesNotContain("RESULT PASS");
        assertThat(claimId("worker-sup-2")).isNotEqualTo(id);
    }

    @Test
    void unconfirmedExitIsNotSuccess() throws Exception {
        String id = JsonPath.read(createJob("idem-alive-00001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-alive")).isEqualTo(id);
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/finish")
                        .header("X-Worker-Id", "worker-alive")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"exit_code":0,"process_exited":false,"timed_out":false,"termination_reason":"COMPLETED"}
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("RUNNING"))
                .andExpect(jsonPath("$.termination_reason").value(nullValue()));
        assertThat(events(id)).doesNotContain("RESULT PASS");
    }

    @Test
    void cancelWinsWhenExitCodeIsZero() throws Exception {
        String id = JsonPath.read(createJob("idem-race-000001", "trusted-sample", "sample-slow"), "$.id");
        assertThat(claimId("worker-race")).isEqualTo(id);
        mockMvc.perform(post("/api/v1/jobs/" + id + "/cancel")).andExpect(status().isOk());
        JobResponse finished = workerJobs.finish(
                "worker-race",
                id,
                new FinishRequest(0, true, false, true, "OUTPUT_LIMIT_EXCEEDED"));
        assertThat(finished.status()).isEqualTo(JobStatus.CANCELLED);
        assertThat(finished.terminationReason()).isEqualTo("CANCELLED");
        assertThat(finished.outputTruncated()).isTrue();
        assertThat(events(id)).doesNotContain("RESULT PASS");
    }

    @Test
    void eventBatchIsStoredOnceAndRejectsADifferentPayload() throws Exception {
        String id = JsonPath.read(createJob("idem-batch-00001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-batch")).isEqualTo(id);
        String body = """
                {"batch_id":"job-batch-b1","lines":[{"stream":"STDOUT","text":"alpha"},{"stream":"STDERR","text":"beta"}]}
                """;
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/events")
                        .header("X-Worker-Id", "worker-batch")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNoContent());
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/events")
                        .header("X-Worker-Id", "worker-batch")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNoContent());
        assertThat(countText(id, "alpha")).isEqualTo(1);
        assertThat(countText(id, "beta")).isEqualTo(1);
        assertThat(jdbcTemplate.queryForObject(
                "select count(*) from job_event_batches where job_id = ? and batch_id = ?",
                Integer.class,
                id,
                "job-batch-b1")).isEqualTo(1);
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/events")
                        .header("X-Worker-Id", "worker-batch")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"batch_id":"job-batch-b1","lines":[{"stream":"STDOUT","text":"other"}]}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("CONFLICT"));
        assertThat(countText(id, "other")).isZero();
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/events")
                        .header("X-Worker-Id", "worker-other")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"batch_id":"job-batch-b2","lines":[{"stream":"STDOUT","text":"stolen"}]}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STATE"));
        assertThat(countText(id, "stolen")).isZero();
        workerJobs.finish("worker-batch", id, new FinishRequest(0, true, false));
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/events")
                        .header("X-Worker-Id", "worker-batch")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"batch_id":"job-batch-b2","lines":[{"stream":"STDOUT","text":"after-finish"}]}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STATE"));
        mockMvc.perform(post("/api/v1/worker/jobs/" + id + "/events")
                        .header("X-Worker-Id", "worker-batch")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isNoContent());
        assertThat(countText(id, "after-finish")).isZero();
        assertThat(jdbcTemplate.queryForObject(
                "select count(*) from job_event_batches where job_id = ? and batch_id = ?",
                Integer.class,
                id,
                "job-batch-b1")).isEqualTo(1);
    }

    @Test
    void incompleteLogStorageDoesNotHideAPassingProcess() throws Exception {
        String id = JsonPath.read(createJob("idem-incompl-001", "trusted-sample", "sample-pass"), "$.id");
        assertThat(claimId("worker-incompl")).isEqualTo(id);
        JobResponse finished = workerJobs.finish(
                "worker-incompl",
                id,
                new FinishRequest(0, true, false, false, "COMPLETED", true));
        assertThat(finished.status()).isEqualTo(JobStatus.SUCCEEDED);
        assertThat(finished.terminationReason()).isEqualTo("COMPLETED");
        assertThat(finished.logStorageIncomplete()).isTrue();
        assertThat(events(id)).contains("로그 일부를 저장하지 못했습니다").contains("RESULT PASS");
    }

    @Test
    void heartbeatMakesTheWorkerVisible() throws Exception {
        mockMvc.perform(post("/api/v1/worker/heartbeat").header("X-Worker-Id", "worker-health"))
                .andExpect(status().isOk());
        mockMvc.perform(get("/api/v1/health"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.worker").value("CONNECTED"));
    }

    private String confirmedBody() throws Exception {
        return mockMvc.perform(get("/api/v1/error-cases/confirmed"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private String caseIdContaining(String fragment) {
        return errorCases.findAll().stream()
                .filter(item -> item.getRawText().contains(fragment))
                .map(ErrorCaseEntity::getId)
                .findFirst()
                .orElseThrow();
    }

    private String claimId(String workerId) {
        return workerJobs.claim(workerId).map(claimed -> claimed.jobId()).orElse("");
    }

    private static String ownerOf(AtomicReference<String> first, AtomicReference<String> second, String id) {
        if (id.equals(first.get())) {
            return "worker-a";
        }
        if (id.equals(second.get())) {
            return "worker-b";
        }
        return "";
    }

    private String createJob(String key, String projectId, String taskId) throws Exception {
        return mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", key)
                        .content("{\"project_id\":\"" + projectId + "\",\"task_id\":\"" + taskId + "\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private int countText(String jobId, String text) {
        Integer count = jdbcTemplate.queryForObject(
                "select count(*) from job_events where job_id = ? and text = ?",
                Integer.class,
                jobId,
                text);
        return count == null ? 0 : count;
    }

    private String events(String jobId) throws Exception {
        return mockMvc.perform(get("/api/v1/jobs/" + jobId + "/events"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private static void runExclusive(
            CountDownLatch ready,
            CountDownLatch start,
            AtomicReference<Throwable> error,
            Runnable action) {
        ready.countDown();
        try {
            if (!start.await(5, TimeUnit.SECONDS)) {
                error.set(new IllegalStateException("start timeout"));
                return;
            }
            action.run();
        } catch (Throwable throwable) {
            error.set(throwable);
        }
    }
}
