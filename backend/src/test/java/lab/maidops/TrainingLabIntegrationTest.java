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
import lab.maidops.domain.ErrorLabel;
import lab.maidops.lab.ClassificationMetrics;
import lab.maidops.lab.ClassificationMetrics.ClassScore;
import lab.maidops.lab.ClassificationMetrics.Report;
import lab.maidops.lab.EvaluationFingerprint;
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

    @Test
    void reloadFlagIsRequiredBeforeAScoreIsStored() throws Exception {
        seedConfirmed("p5c");
        String runId = JsonPath.read(
                mockMvc.perform(post("/api/v1/training-runs"))
                        .andExpect(status().isCreated())
                        .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8),
                "$.id");
        String modelId = JsonPath.read(claim("trainer-flag"), "$.reserved_model_id");
        Files.writeString(MODEL_DIR.resolve(modelId + ".pt"), "not-a-loaded-checkpoint");
        String body = completeBody(runId).replace("\"checkpoint_evaluated\": true", "\"checkpoint_evaluated\": false");
        mockMvc.perform(post("/api/v1/trainer/runs/" + runId + "/complete")
                        .header("X-Trainer-Id", "trainer-flag")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isBadRequest());
        assertThat(jdbcTemplate.queryForObject("select count(*) from model_versions", Integer.class)).isZero();
        assertThat(jdbcTemplate.queryForObject(
                "select status from training_runs where id = ?",
                String.class,
                runId)).isEqualTo("RUNNING");
    }

    @Test
    void legacyMetricsCannotReplaceTheCurrentDefault() throws Exception {
        seedConfirmed("p5d");
        String created = mockMvc.perform(post("/api/v1/training-runs"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        String runId = JsonPath.read(created, "$.id");
        String modelId = JsonPath.read(claim("trainer-legacy"), "$.reserved_model_id");
        Files.writeString(MODEL_DIR.resolve(modelId + ".pt"), "not-a-loaded-checkpoint");
        complete(modelId, "trainer-legacy", runId);
        mockMvc.perform(post("/api/v1/model-versions/" + modelId + "/select-default"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.is_default").value(true));
        jdbcTemplate.update(
                """
                insert into training_runs (
                    id, created_at, status, dataset_fingerprint, label_schema_version, embedding_id, split_policy
                ) values ('run-legacy01', ?, 'FAILED', ?, 'labels-1', 'hashing-char-ngram-v1', 'split-1')
                """,
                Timestamp.from(Instant.parse("2026-10-13T00:00:00Z")),
                "c".repeat(64));
        Files.writeString(MODEL_DIR.resolve("mv-00000099.pt"), "legacy-bytes");
        jdbcTemplate.update(
                """
                insert into model_versions (
                    id, training_run_id, created_at, embedding_id, label_schema_version, dataset_fingerprint,
                    code_version, device, seed, config_json, metrics_json, model_file, checksum_sha256,
                    byte_size, is_default
                ) values (
                    'mv-00000099', 'run-legacy01', ?, 'hashing-char-ngram-v1', 'labels-1', ?,
                    'unknown', 'cpu', 42, '{}', '{"macro_f1":1.0,"baseline_macro_f1":0.0}', 'mv-00000099.pt', ?, ?, false
                )
                """,
                Timestamp.from(Instant.parse("2026-10-13T00:00:02Z")),
                "d".repeat(64),
                "ab".repeat(32),
                12);
        mockMvc.perform(post("/api/v1/model-versions/mv-00000099/select-default"))
                .andExpect(status().isConflict());
        assertThat(jdbcTemplate.queryForObject(
                "select is_default from model_versions where id = ?",
                Boolean.class,
                modelId)).isTrue();
        assertThat(jdbcTemplate.queryForObject(
                "select is_default from model_versions where id = ?",
                Boolean.class,
                "mv-00000099")).isFalse();
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
        // 서버 계약만 확인한다. 이 파일 바이트는 PyTorch 체크포인트가 아니고 서버도 로드하지 않는다.
        // checkpoint_evaluated는 학습기 표시다. 이 테스트가 그 표시를 보낸다고 실제 재로드 평가가 된 것은 아니다.
        String body = completeBody(runId);
        return mockMvc.perform(post("/api/v1/trainer/runs/" + runId + "/complete")
                        .header("X-Trainer-Id", trainerId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(modelId))
                .andExpect(jsonPath("$.is_default").value(false))
                .andExpect(jsonPath("$.metric_policy").value("supported-class-macro-f1-v2"))
                .andExpect(jsonPath("$.checkpoint_evaluated").value(true))
                .andExpect(jsonPath("$.probability_note").value(org.hamcrest.Matchers.containsString("정답 확률")))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private String completeBody(String runId) {
        Report report = ClassificationMetrics.fromConfusion(testMatrix(runId));
        String scores = scores(report);
        String matrix = matrix(report.confusion());
        String fingerprint = evaluationFingerprint(runId);
        String included = report.perClass().stream()
                .filter(ClassScore::includedInMacro)
                .map(score -> "\"" + score.label().name() + "\"")
                .reduce((left, right) -> left + "," + right)
                .orElse("");
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
                  "baseline_confusion_matrix": %s,
                  "metric_policy": "supported-class-macro-f1-v2",
                  "label_order": ["DB_CONNECTION","AUTH_PERMISSION","EXTERNAL_NETWORK","INPUT_VALIDATION","OTHER"],
                  "included_labels": [%s],
                  "evaluation_sample_count": %d,
                  "evaluation_fingerprint": "%s",
                  "checkpoint_evaluated": true
                }
                """.formatted(
                Double.toString(report.macroF1()),
                scores,
                matrix,
                Double.toString(report.macroF1()),
                scores,
                matrix,
                included,
                report.perClass().stream().mapToInt(ClassScore::support).sum(),
                fingerprint);
        return body;
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
                    .append(",\"predicted_count\":")
                    .append(score.predictedCount())
                    .append(",\"false_positives\":")
                    .append(score.falsePositives())
                    .append(",\"included_in_macro\":")
                    .append(score.includedInMacro())
                    .append('}');
        }
        return builder.append(']').toString();
    }

    private int[][] testMatrix(String runId) {
        int[][] matrix = new int[ErrorLabel.values().length][ErrorLabel.values().length];
        jdbcTemplate.query(
                """
                select label from training_examples
                where training_run_id = ? and split = 'TEST'
                order by error_case_id
                """,
                rs -> {
                    int index = ErrorLabel.valueOf(rs.getString("label")).ordinal();
                    matrix[index][index] += 1;
                },
                runId);
        return matrix;
    }

    private String evaluationFingerprint(String runId) {
        List<EvaluationFingerprint.Row> rows = new ArrayList<>();
        jdbcTemplate.query(
                """
                select e.error_case_id, e.label, c.raw_text
                from training_examples e
                join error_cases c on c.id = e.error_case_id
                where e.training_run_id = ? and e.split = 'TEST'
                order by e.error_case_id
                """,
                rs -> {
                    rows.add(new EvaluationFingerprint.Row(
                            rs.getString("error_case_id"),
                            rs.getString("label"),
                            rs.getString("raw_text")));
                },
                runId);
        return EvaluationFingerprint.of(rows);
    }

    private static String matrix(int[][] source) {
        StringBuilder builder = new StringBuilder("[");
        for (int row = 0; row < source.length; row++) {
            if (row > 0) {
                builder.append(',');
            }
            builder.append('[');
            for (int column = 0; column < source[row].length; column++) {
                if (column > 0) {
                    builder.append(',');
                }
                builder.append(source[row][column]);
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
