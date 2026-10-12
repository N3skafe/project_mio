package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.hamcrest.Matchers.nullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HexFormat;

import com.jayway.jsonpath.JsonPath;
import lab.maidops.errorcase.ErrorCaseRepository;
import lab.maidops.lab.ModelDraftService;
import lab.maidops.worker.WorkerJobService;
import lab.maidops.worker.WorkerJobService.FinishRequest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class ModelDraftIntegrationTest extends PostgresTestSupport {
    private static final Path MODEL_DIR = createDir();

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private WorkerJobService workerJobs;

    @Autowired
    private ErrorCaseRepository errorCases;

    @Autowired
    private ModelDraftService drafts;

    @DynamicPropertySource
    static void paths(DynamicPropertyRegistry registry) {
        registry.add("maidops.model-dir", MODEL_DIR::toString);
        Path root = Path.of("..", "fixtures", "trusted-projects").toAbsolutePath().normalize();
        registry.add("maidops.workspace-root", root::toString);
    }

    @AfterEach
    void clearDrafts() {
        jdbcTemplate.update("delete from draft_inferences");
        jdbcTemplate.update("delete from label_revisions");
        jdbcTemplate.update("delete from resolution_records");
        jdbcTemplate.update("delete from error_cases");
        jdbcTemplate.update("delete from model_versions");
        jdbcTemplate.update("delete from training_runs");
    }

    @Test
    void defaultModelDraftStaysUnconfirmedUntilTheTrainerReturnsALabel() throws Exception {
        String withoutModel = failJob("draft-rule-job");
        String ruleCase = caseForJob(withoutModel);
        mockMvc.perform(get("/api/v1/error-cases/" + ruleCase))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.inference_state").value("READY"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.score").doesNotExist());

        installDefaultModel();
        String jobId = failJob("draft-model-job");
        String caseId = caseForJob(jobId);
        mockMvc.perform(get("/api/v1/error-cases/" + caseId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_source").value("MODEL"))
                .andExpect(jsonPath("$.inference_state").value("PENDING"))
                .andExpect(jsonPath("$.draft_label").value(nullValue()))
                .andExpect(jsonPath("$.current_label").value(nullValue()))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.model_version_id").value("mv-00000007"))
                .andExpect(jsonPath("$.score").doesNotExist());
        mockMvc.perform(get("/api/v1/error-cases/confirmed"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[?(@.id == '" + caseId + "')]").isEmpty());
        mockMvc.perform(post("/api/v1/error-cases/" + caseId + "/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"APPROVE\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("모델 초안이 아직 없습니다")));

        String claimed = mockMvc.perform(post("/api/v1/trainer/inferences/claim")
                        .header("X-Trainer-Id", "trainer-draft"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.model_file").value("mv-00000007.pt"))
                .andExpect(jsonPath("$.error_case_id").value(caseId))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        String inferenceId = JsonPath.read(claimed, "$.inference_id");
        mockMvc.perform(post("/api/v1/trainer/inferences/" + inferenceId + "/complete")
                        .header("X-Trainer-Id", "trainer-draft")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"label\":\"INPUT_VALIDATION\"}"))
                .andExpect(status().isNoContent());
        String ready = mockMvc.perform(get("/api/v1/error-cases/" + caseId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_source").value("MODEL"))
                .andExpect(jsonPath("$.draft_label").value("INPUT_VALIDATION"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.revisions[0].source").value("MODEL"))
                .andExpect(jsonPath("$.score").doesNotExist())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(ready).contains("softmax 출력은 보정된 정답 확률이 아닙니다");
        mockMvc.perform(post("/api/v1/trainer/inferences/claim").header("X-Trainer-Id", "trainer-draft"))
                .andExpect(status().isNoContent());

        String waitingJob = failJob("draft-expire-job");
        String waitingCase = caseForJob(waitingJob);
        jdbcTemplate.update(
                "update draft_inferences set lease_expires_at = ? where error_case_id = ?",
                Timestamp.from(Instant.now().minusSeconds(5)),
                waitingCase);
        drafts.expireLeases();
        mockMvc.perform(get("/api/v1/error-cases/" + waitingCase))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.inference_state").value("READY"))
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()))
                .andExpect(jsonPath("$.revisions[0].note", org.hamcrest.Matchers.containsString("자동으로 다시 추론하지 않습니다")));
        mockMvc.perform(post("/api/v1/trainer/inferences/claim").header("X-Trainer-Id", "trainer-draft"))
                .andExpect(status().isNoContent());
    }

    private void installDefaultModel() throws Exception {
        byte[] bytes = "maidops-draft-model".getBytes(StandardCharsets.UTF_8);
        String checksum = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        Files.write(MODEL_DIR.resolve("mv-00000007.pt"), bytes);
        jdbcTemplate.update(
                """
                insert into training_runs (
                    id, created_at, status, dataset_fingerprint, label_schema_version, embedding_id, split_policy
                ) values ('run-draft0001', ?, 'FAILED', ?, 'labels-1', 'hashing-char-ngram-v1', 'split-1')
                """,
                Timestamp.from(Instant.parse("2026-10-13T00:00:00Z")),
                "a".repeat(64));
        jdbcTemplate.update(
                """
                insert into model_versions (
                    id, training_run_id, created_at, embedding_id, label_schema_version, dataset_fingerprint,
                    code_version, device, seed, config_json, metrics_json, model_file, checksum_sha256,
                    byte_size, is_default
                ) values (
                    'mv-00000007', 'run-draft0001', ?, 'hashing-char-ngram-v1', 'labels-1', ?,
                    'unknown', 'cpu', 42, '{}', '{}', 'mv-00000007.pt', ?, ?, true
                )
                """,
                Timestamp.from(Instant.parse("2026-10-13T00:00:01Z")),
                "b".repeat(64),
                checksum,
                bytes.length);
    }

    private String failJob(String key) throws Exception {
        String id = JsonPath.read(createJob(key), "$.id");
        assertThat(workerJobs.claim("worker-" + key).map(claimed -> claimed.jobId()).orElse("")).isEqualTo(id);
        workerJobs.finish("worker-" + key, id, new FinishRequest(2, true, false));
        return id;
    }

    private String createJob(String key) throws Exception {
        return mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", key)
                        .content("{\"project_id\":\"trusted-sample\",\"task_id\":\"sample-fail\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private String caseForJob(String jobId) {
        return errorCases.findAll().stream()
                .filter(item -> jobId.equals(item.getJobId()))
                .map(item -> item.getId())
                .findFirst()
                .orElseThrow();
    }

    private static Path createDir() {
        try {
            return Files.createTempDirectory("maidops-drafts");
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }
}
