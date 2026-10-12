package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import com.jayway.jsonpath.JsonPath;
import lab.maidops.lab.ClassificationMetrics;
import lab.maidops.lab.ClassificationMetrics.ClassScore;
import lab.maidops.lab.ClassificationMetrics.Report;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
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
class TrainingLabIntegrationTest extends PostgresTestSupport {
    private static final Path MODEL_DIR = createModelDir();
    private static final String[] WORDS = {
            "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
            "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
            "quebec", "romeo", "sierra", "tango"
    };
    private static final int[][] MATRIX = {
            {2, 0, 0, 0, 0},
            {0, 1, 1, 0, 0},
            {0, 0, 0, 0, 0},
            {0, 0, 0, 1, 0},
            {1, 0, 0, 0, 1}
    };

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private lab.maidops.lab.TrainingService training;

    @DynamicPropertySource
    static void modelDirectory(DynamicPropertyRegistry registry) {
        registry.add("maidops.model-dir", MODEL_DIR::toString);
    }

    @BeforeEach
    @AfterEach
    void clearLabRows() {
        jdbcTemplate.update("delete from training_examples");
        jdbcTemplate.update("delete from model_versions");
        jdbcTemplate.update("delete from training_runs");
        jdbcTemplate.update("delete from dataset_split_anchors");
        jdbcTemplate.update("delete from resolution_records");
        jdbcTemplate.update("delete from label_revisions");
        jdbcTemplate.update("delete from draft_inferences");
        jdbcTemplate.update("delete from error_cases");
    }

    @Test
    void insufficientConfirmedDataDoesNotCreateAScore() throws Exception {
        insertCase("draft-only", createJob("p5-draft-job", "demo-api", "api-db-check"), "draft only zeta", "OTHER", "DRAFT");
        insertCase("defer-only", createJob("p5-defer-job", "demo-api", "api-db-check"), "defer only zeta", "OTHER", "DEFERRED");
        String body = mockMvc.perform(get("/api/v1/lab/status"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.eligible").value(false))
                .andExpect(jsonPath("$.confirmed_count").value(0))
                .andExpect(jsonPath("$.draft_count").value(1))
                .andExpect(jsonPath("$.deferred_count").value(1))
                .andExpect(jsonPath("$.download_required").value(false))
                .andExpect(jsonPath("$.latest_model").doesNotExist())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(body).contains("확정 사례가 0건").contains("학습 수에 넣지 않았습니다").doesNotContain("macro_f1");
        mockMvc.perform(post("/api/v1/training-runs"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STATE"));
        assertThat(jdbcTemplate.queryForObject("select count(*) from training_runs", Integer.class)).isZero();
        assertThat(jdbcTemplate.queryForObject("select count(*) from model_versions", Integer.class)).isZero();
    }

    @Test
    void trainingDoesNotReplaceTheDefaultModel() throws Exception {
        seedConfirmed("p5a");
        insertCase("p5a-draft", createJob("p5a-draft-job", "demo-api", "api-db-check"), "draft stays out", "OTHER", "DRAFT");
        String created = mockMvc.perform(post("/api/v1/training-runs"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(created).contains("\"status\":\"QUEUED\"").doesNotContain("macro_f1");
        String runId = JsonPath.read(created, "$.id");
        assertThat(jdbcTemplate.queryForObject(
                "select count(*) from training_examples where error_case_id = 'p5a-draft'",
                Integer.class)).isZero();
        assertThat(jdbcTemplate.queryForObject(
                """
                select count(*) from (
                    select group_key from training_examples
                    where training_run_id = ?
                    group by group_key
                    having count(distinct split) > 1
                ) leaked
                """,
                Integer.class,
                runId)).isZero();

        String claimed = claim("trainer-a");
        String modelId = JsonPath.read(claimed, "$.reserved_model_id");
        Files.writeString(MODEL_DIR.resolve(modelId + ".pt"), "not-a-loaded-checkpoint");
        String firstModel = complete(modelId, "trainer-a", runId);
        assertThat(firstModel).contains("\"is_default\":false");
        assertThat(JsonPath.<Boolean>read(
                mockMvc.perform(get("/api/v1/lab/status")).andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8),
                "$.latest_model.is_default")).isFalse();

        mockMvc.perform(post("/api/v1/model-versions/" + modelId + "/select-default"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.is_default").value(true));

        insertCase(
                "p5a-new",
                createJob("p5a-new-job", "demo-api", "api-db-check"),
                "unique failure token uniform end",
                "OTHER",
                "APPROVED");
        String secondRun = JsonPath.read(
                mockMvc.perform(post("/api/v1/training-runs"))
                        .andExpect(status().isCreated())
                        .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8),
                "$.id");
        String secondClaim = claim("trainer-b");
        List<String> stillTest = jdbcTemplate.queryForList(
                """
                select e2.error_case_id
                from training_examples e1
                join training_examples e2
                  on e2.error_case_id = e1.error_case_id
                 and e2.training_run_id = ?
                where e1.training_run_id = ? and e1.split = 'TEST' and e2.split = 'TEST'
                """,
                String.class,
                secondRun,
                runId);
        assertThat(stillTest).isNotEmpty();
        assertThat(jdbcTemplate.queryForObject(
                "select split from training_examples where training_run_id = ? and error_case_id = 'p5a-new'",
                String.class,
                secondRun)).isEqualTo("TRAIN");
        String secondModel = JsonPath.read(secondClaim, "$.reserved_model_id");
        Files.writeString(MODEL_DIR.resolve(secondModel + ".pt"), "second-checkpoint");
        complete(secondModel, "trainer-b", secondRun);
        assertThat(jdbcTemplate.queryForObject(
                "select is_default from model_versions where id = ?",
                Boolean.class,
                modelId)).isTrue();
        assertThat(jdbcTemplate.queryForObject(
                "select is_default from model_versions where id = ?",
                Boolean.class,
                secondModel)).isFalse();
    }

    @Test
    void expiredTrainingLeaseIsNotRequeued() throws Exception {
        seedConfirmed("p5b");
        String runId = JsonPath.read(
                mockMvc.perform(post("/api/v1/training-runs"))
                        .andExpect(status().isCreated())
                        .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8),
                "$.id");
        claim("trainer-lease");
        jdbcTemplate.update(
                "update training_runs set lease_expires_at = ? where id = ?",
                Timestamp.from(Instant.parse("2020-01-01T00:00:00Z")),
                runId);
        training.expireLeases();
        mockMvc.perform(get("/api/v1/training-runs/" + runId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.status").value("FAILED"))
                .andExpect(jsonPath("$.error_message").value(org.hamcrest.Matchers.containsString("자동으로 다시 학습하지 않습니다")))
                .andExpect(jsonPath("$.model").doesNotExist());
        mockMvc.perform(post("/api/v1/trainer/claim").header("X-Trainer-Id", "trainer-next"))
                .andExpect(status().isNoContent());
        assertThat(jdbcTemplate.queryForObject("select count(*) from model_versions", Integer.class)).isZero();
    }

    private String claim(String trainerId) throws Exception {
        String body = claimBody(trainerId);
        assertThat(body).contains("hashing-char-ngram-v1").contains("\"seed\":42");
        return body;
    }

    private String claimBody(String trainerId) throws Exception {
        return mockMvc.perform(post("/api/v1/trainer/claim").header("X-Trainer-Id", trainerId))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private String complete(String modelId, String trainerId, String runId) throws Exception {
        Report report = ClassificationMetrics.fromConfusion(MATRIX);
        String scores = scores(report);
        String matrix = matrix();
        String body = """
                {
                  "embedding_id": "hashing-char-ngram-v1",
                  "label_schema_version": "labels-1",
                  "code_version": "unknown",
                  "device": "cpu",
                  "seed": 42,
                  "config": {
                    "embedding_dim": 256,
                    "hidden_dim": 64,
                    "epochs_ran": 3,
                    "max_epochs": 40,
                    "batch_size": 16,
                    "learning_rate": 0.001,
                    "dropout": 0.0
                  },
                  "macro_f1": %s,
                  "per_class": %s,
                  "confusion_matrix": %s,
                  "baseline_macro_f1": %s,
                  "baseline_per_class": %s,
                  "baseline_confusion_matrix": %s
                }
                """.formatted(
                Double.toString(report.macroF1()),
                scores,
                matrix,
                Double.toString(report.macroF1()),
                scores,
                matrix);
        return mockMvc.perform(post("/api/v1/trainer/runs/" + runId + "/complete")
                        .header("X-Trainer-Id", trainerId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(modelId))
                .andExpect(jsonPath("$.is_default").value(false))
                .andExpect(jsonPath("$.probability_note").value(org.hamcrest.Matchers.containsString("정답 확률")))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private static String scores(Report report) {
        StringBuilder builder = new StringBuilder("[");
        for (int index = 0; index < report.perClass().size(); index++) {
            ClassScore score = report.perClass().get(index);
            if (index > 0) {
                builder.append(',');
            }
            builder.append("{\"label\":\"")
                    .append(score.label().name())
                    .append("\",\"precision\":")
                    .append(number(score.precision()))
                    .append(",\"recall\":")
                    .append(number(score.recall()))
                    .append(",\"f1\":")
                    .append(number(score.f1()))
                    .append(",\"support\":")
                    .append(score.support())
                    .append('}');
        }
        return builder.append(']').toString();
    }

    private static String matrix() {
        StringBuilder builder = new StringBuilder("[");
        for (int row = 0; row < MATRIX.length; row++) {
            if (row > 0) {
                builder.append(',');
            }
            builder.append('[');
            for (int column = 0; column < MATRIX[row].length; column++) {
                if (column > 0) {
                    builder.append(',');
                }
                builder.append(MATRIX[row][column]);
            }
            builder.append(']');
        }
        return builder.append(']').toString();
    }

    private static String number(Double value) {
        return value == null ? "null" : Double.toString(value);
    }

    private void seedConfirmed(String prefix) throws Exception {
        for (int index = 0; index < WORDS.length; index++) {
            String label = index % 2 == 0 ? "DB_CONNECTION" : "AUTH_PERMISSION";
            String jobId = createJob(prefix + "-job-" + index, "demo-api", "api-db-check");
            insertCase(
                    prefix + "-case-" + index,
                    jobId,
                    "unique failure token " + WORDS[index] + " end",
                    label,
                    "APPROVED");
        }
    }

    private void insertCase(String caseId, String jobId, String text, String label, String reviewStatus) {
        jdbcTemplate.update(
                """
                insert into error_cases (
                    id, job_id, project_id, raw_text, draft_label, draft_source, current_label,
                    review_status, origin, created_at, rule_version
                ) values (?, ?, 'demo-api', ?, 'OTHER', 'RULE_BASED', ?, ?, 'SESSION', ?, 'rules-1')
                """,
                caseId,
                jobId,
                text,
                label,
                reviewStatus,
                Timestamp.from(Instant.now()));
    }

    private String createJob(String key, String projectId, String taskId) throws Exception {
        String body = mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", key)
                        .content("{\"project_id\":\"" + projectId + "\",\"task_id\":\"" + taskId + "\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        return JsonPath.read(body, "$.id");
    }

    private static Path createModelDir() {
        try {
            return Files.createTempDirectory("maidops-models");
        } catch (java.io.IOException exception) {
            throw new IllegalStateException(exception);
        }
    }
}
