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
import java.util.List;

import com.jayway.jsonpath.JsonPath;
import lab.maidops.worker.WorkerJobService;
import lab.maidops.worker.WorkerJobService.FinishRequest;
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
class IntakeIntegrationTest extends PostgresTestSupport {
    private static final Path MODEL_DIR = createModelDir();

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private WorkerJobService workerJobs;

    @DynamicPropertySource
    static void workspace(DynamicPropertyRegistry registry) {
        Path root = Path.of("..", "fixtures", "trusted-projects").toAbsolutePath().normalize();
        registry.add("maidops.workspace-root", root::toString);
        registry.add("maidops.model-dir", MODEL_DIR::toString);
    }

    private static Path createModelDir() {
        try {
            return Files.createTempDirectory("maidops-intake-models");
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    @Test
    void registersATrustedProjectAndTaskThenQueuesAJob() throws Exception {
        mockMvc.perform(post("/api/v1/projects")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"id\":\"user-lab\",\"display_name\":\"사용자 실험\",\"summary\":\"직접 등록\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.id").value("user-lab"))
                .andExpect(jsonPath("$.name").value("사용자 실험"))
                .andExpect(jsonPath("$.default_task_id").value(nullValue()));
        mockMvc.perform(post("/api/v1/projects")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"id\":\"user-lab\",\"name\":\"다시\"}"))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STATE"));
        mockMvc.perform(post("/api/v1/projects/user-lab/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-pass","name":"통과 점검","plan_text":"등록된 스크립트만 실행합니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.argv_json").value("[\"{python}\",\"pass_check.py\"]"))
                .andExpect(jsonPath("$.relative_workdir").value("sample"));
        mockMvc.perform(get("/api/v1/projects/user-lab"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.default_task_id").value("user-pass"));
        mockMvc.perform(get("/api/v1/projects"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[?(@.id == 'user-lab')].name").value("사용자 실험"))
                .andExpect(jsonPath("$.items[?(@.id == 'trusted-sample')]").exists());
        String userJob = JsonPath.read(mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", "idem-intake-user-1")
                        .content("{\"project_id\":\"user-lab\",\"task_id\":\"user-pass\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("QUEUED"))
                .andExpect(jsonPath("$.task_id").value("user-pass"))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8), "$.id");
        String seedJob = JsonPath.read(mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", "idem-intake-seed-1")
                        .content("{\"project_id\":\"trusted-sample\",\"task_id\":\"sample-pass\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("QUEUED"))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8), "$.id");
        mockMvc.perform(post("/api/v1/jobs/" + userJob + "/cancel")).andExpect(status().isOk());
        mockMvc.perform(post("/api/v1/jobs/" + seedJob + "/cancel")).andExpect(status().isOk());
    }

    @Test
    void rejectsPathsOutsideTheWorkspaceAndBadArgv() throws Exception {
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-escape","name":"탈출","plan_text":"거절되어야 합니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"..","timeout_seconds":10}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("허용 경로")));
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-binary","name":"바이너리","plan_text":"거절되어야 합니다.",
                                 "argv_json":["python","pass_check.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("{python}")));
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-timeout","name":"시간","plan_text":"거절되어야 합니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"sample","timeout_seconds":0}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.example").value("10"));
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-missing","name":"없는 파일","plan_text":"거절되어야 합니다.",
                                 "argv_json":["{python}","missing_check.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("스크립트")));
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-absolute","name":"절대 경로","plan_text":"거절되어야 합니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"C:/Windows","timeout_seconds":10}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("허용 경로")));
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-argv-escape","name":"argv 탈출","plan_text":"거절되어야 합니다.",
                                 "argv_json":["{python}","../../outside.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-global-once","name":"전역 id","plan_text":"한 번만 등록됩니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isCreated());
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-global-once","name":"다시","plan_text":"거절되어야 합니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STATE"))
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("작업 id는 전체에서 유일")));
    }

    @Test
    void importsAFailureLogWithoutCreatingAJob() throws Exception {
        List<String> defaults = jdbcTemplate.queryForList(
                "select id from model_versions where is_default",
                String.class);
        jdbcTemplate.update("update model_versions set is_default = false");
        try {
            importAndReview(jobsBeforeCount());
        } finally {
            for (String id : defaults) {
                jdbcTemplate.update("update model_versions set is_default = false");
                jdbcTemplate.update("update model_versions set is_default = true where id = ?", id);
            }
        }
    }

    private void importAndReview(int jobsBefore) throws Exception {
        String body = mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"project_id":"trusted-sample","title":"지난 배포",
                                 "raw_log":"org.postgresql.util.PSQLException: Connection to localhost:5432 refused token=hunter2"}
                                """))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(body).contains("\"origin\":\"IMPORT\"");
        assertThat(body).contains("\"job_id\":null");
        assertThat(body).contains("\"draft_source\":\"RULE_BASED\"");
        assertThat(body).contains("\"draft_label\":\"DB_CONNECTION\"");
        assertThat(body).contains("rules-1");
        assertThat(body).contains("지난 배포");
        assertThat(body).doesNotContain("hunter2");
        assertThat(body).contains("[REDACTED]");
        assertThat(jdbcTemplate.queryForObject("select count(*) from jobs", Integer.class)).isEqualTo(jobsBefore);
        String caseId = JsonPath.read(body, "$.id");
        mockMvc.perform(post("/api/v1/error-cases/" + caseId + "/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"REVISE\",\"label\":\"OTHER\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.current_label").value("OTHER"))
                .andExpect(jsonPath("$.confirmed_label").value("OTHER"))
                .andExpect(jsonPath("$.origin").value("IMPORT"))
                .andExpect(jsonPath("$.revisions[-1].source").value("USER"));
        mockMvc.perform(post("/api/v1/error-cases/" + caseId + "/resolutions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cause\":\"phase6-import-cause\",\"method\":\"포트를 확인합니다\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.origin").value("SESSION"));
        mockMvc.perform(get("/api/v1/search").param("q", "phase6-import-cause"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].kind").value("RESOLUTION"));

        String deferred = mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"trusted-sample\",\"lines\":[\"boom from import\"]}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.origin").value("IMPORT"))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        String deferredId = JsonPath.read(deferred, "$.id");
        mockMvc.perform(post("/api/v1/error-cases/" + deferredId + "/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"DEFER\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.confirmed_label").value(nullValue()));
        String confirmed = mockMvc.perform(get("/api/v1/error-cases/confirmed"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(confirmed).doesNotContain(deferredId);
    }

    private int jobsBeforeCount() {
        Integer count = jdbcTemplate.queryForObject("select count(*) from jobs", Integer.class);
        return count == null ? 0 : count;
    }

    @Test
    void importFollowsTheDefaultModelContract() throws Exception {
        List<String> defaults = jdbcTemplate.queryForList(
                "select id from model_versions where is_default",
                String.class);
        jdbcTemplate.update("update model_versions set is_default = false");
        try {
            installDefaultModel(false);
            String missingFile = importBody("missing model file");
            assertThat(missingFile).contains("\"origin\":\"IMPORT\"").contains("\"job_id\":null");
            assertThat(missingFile).contains("\"draft_source\":\"RULE_BASED\"");
            assertThat(missingFile).contains("\"inference_state\":\"READY\"");
            assertThat(missingFile).contains("기본 모델 파일이 없습니다");
            String missingCaseId = JsonPath.read(missingFile, "$.id");
            jdbcTemplate.update("delete from label_revisions where error_case_id = ?", missingCaseId);
            jdbcTemplate.update("delete from error_cases where id = ?", missingCaseId);
            jdbcTemplate.update("delete from model_versions where id = 'mv-00000061'");
            jdbcTemplate.update("delete from training_runs where id = 'run-intake001'");

            installDefaultModel(true);
            String pending = importBody("model file present");
            assertThat(pending).contains("\"origin\":\"IMPORT\"").contains("\"job_id\":null");
            assertThat(pending).contains("\"draft_source\":\"MODEL\"");
            assertThat(pending).contains("\"inference_state\":\"PENDING\"");
            assertThat(pending).contains("\"draft_label\":null");
            assertThat(pending).contains("\"model_version_id\":\"mv-00000061\"");
        } finally {
            jdbcTemplate.update("delete from draft_inferences where model_version_id = 'mv-00000061'");
            jdbcTemplate.update("delete from model_versions where id = 'mv-00000061'");
            jdbcTemplate.update("delete from training_runs where id = 'run-intake001'");
            jdbcTemplate.update("update model_versions set is_default = false");
            for (String id : defaults) {
                jdbcTemplate.update("update model_versions set is_default = true where id = ?", id);
            }
        }
    }

    @Test
    void registeredTaskCanBeClaimedAndFinished() throws Exception {
        jdbcTemplate.update("update jobs set status = 'CANCELLED', finished_at = now() where status = 'QUEUED'");
        mockMvc.perform(post("/api/v1/projects/trusted-sample/tasks")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {"id":"user-smoke","name":"스모크","plan_text":"등록된 스크립트를 claim합니다.",
                                 "argv_json":["{python}","pass_check.py"],"relative_workdir":"sample","timeout_seconds":10}
                                """))
                .andExpect(status().isCreated());
        String jobId = JsonPath.read(mockMvc.perform(post("/api/v1/jobs")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("Idempotency-Key", "idem-intake-smoke-1")
                        .content("{\"project_id\":\"trusted-sample\",\"task_id\":\"user-smoke\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.status").value("QUEUED"))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8), "$.id");
        assertThat(workerJobs.claim("worker-intake-smoke").map(claimed -> claimed.jobId()).orElse(""))
                .isEqualTo(jobId);
        assertThat(workerJobs.finish("worker-intake-smoke", jobId, new FinishRequest(0, true, false)).status().name())
                .isEqualTo("SUCCEEDED");
    }

    private String importBody(String rawLog) throws Exception {
        return mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"trusted-sample\",\"raw_log\":\"" + rawLog + "\"}"))
                .andExpect(status().isCreated())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
    }

    private void installDefaultModel(boolean writeFile) throws Exception {
        byte[] bytes = "maidops-intake-model".getBytes(StandardCharsets.UTF_8);
        String checksum = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        if (writeFile) {
            Files.write(MODEL_DIR.resolve("mv-00000061.pt"), bytes);
        } else {
            Files.deleteIfExists(MODEL_DIR.resolve("mv-00000061.pt"));
        }
        jdbcTemplate.update(
                """
                insert into training_runs (
                    id, created_at, status, dataset_fingerprint, label_schema_version, embedding_id, split_policy
                ) values ('run-intake001', ?, 'FAILED', ?, 'labels-1', 'hashing-char-ngram-v1', 'split-1')
                """,
                Timestamp.from(Instant.parse("2026-11-10T00:00:00Z")),
                "c".repeat(64));
        jdbcTemplate.update(
                """
                insert into model_versions (
                    id, training_run_id, created_at, embedding_id, label_schema_version, dataset_fingerprint,
                    code_version, device, seed, config_json, metrics_json, model_file, checksum_sha256,
                    byte_size, is_default
                ) values (
                    'mv-00000061', 'run-intake001', ?, 'hashing-char-ngram-v1', 'labels-1', ?,
                    'unknown', 'cpu', 7, '{}', '{}', 'mv-00000061.pt', ?, ?, true
                )
                """,
                Timestamp.from(Instant.parse("2026-11-10T00:00:01Z")),
                "d".repeat(64),
                checksum,
                bytes.length);
    }

    @Test
    void rejectsEmptyOversizedAndUnknownImports() throws Exception {
        mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"trusted-sample\",\"raw_log\":\"   \"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
        mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"trusted-sample\",\"raw_log\":\"" + "x".repeat(8001) + "\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.message").value(org.hamcrest.Matchers.containsString("8000")));
        mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"missing-project\",\"raw_log\":\"boom\"}"))
                .andExpect(status().isNotFound())
                .andExpect(jsonPath("$.code").value("NOT_FOUND"));
    }
}
