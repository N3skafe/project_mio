package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.nio.charset.StandardCharsets;

import com.jayway.jsonpath.JsonPath;
import lab.maidops.search.SimilarSearchService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.MockMvc;

@SpringBootTest
@AutoConfigureMockMvc
class SimilarSearchIntegrationTest extends PostgresTestSupport {
    private static final String STORED =
            "org.postgresql.util.PSQLException: Connection to localhost:5432 refused phase7-marker";
    private static final String QUERY = "Connection to localhost:5432 refused phase7-marker";

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void similarLogCitesTheConfirmedResolutionAndIgnoresDrafts() throws Exception {
        jdbcTemplate.update("update model_versions set is_default = false");
        String created = mockMvc.perform(post("/api/v1/error-cases/import")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"project_id\":\"trusted-sample\",\"raw_log\":\"" + STORED + "\"}"))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.draft_source").value("RULE_BASED"))
                .andExpect(jsonPath("$.rule_version").value("rules-1"))
                .andExpect(jsonPath("$.matched_keyword").value("postgresql"))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        String caseId = JsonPath.read(created, "$.id");
        String draftAnswer = mockMvc.perform(post("/api/v1/search/similar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"raw_log\":\"" + QUERY + "\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.embedding_id").value("hashing-char-ngram-v1"))
                .andExpect(jsonPath("$.similarity_note").value(org.hamcrest.Matchers.containsString("정답 확률이 아닙니다")))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(draftAnswer).contains(SimilarSearchService.EMPTY_ANSWER);
        assertThat(draftAnswer).doesNotContain(caseId);

        mockMvc.perform(post("/api/v1/error-cases/" + caseId + "/reviews")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"decision\":\"APPROVE\"}"))
                .andExpect(status().isOk());
        String resolutionId = JsonPath.read(mockMvc.perform(post("/api/v1/error-cases/" + caseId + "/resolutions")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"cause\":\"phase7-cause-socket\",\"method\":\"phase7-method-port\"}"))
                .andExpect(status().isOk())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8), "$.id");

        String advice = mockMvc.perform(post("/api/v1/search/similar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"raw_log\":\"" + QUERY + "\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hits[0].kind").value("RESOLUTION"))
                .andExpect(jsonPath("$.hits[0].id").value(resolutionId))
                .andExpect(jsonPath("$.hits[0].cause").value("phase7-cause-socket"))
                .andExpect(jsonPath("$.hits[0].method").value("phase7-method-port"))
                .andExpect(jsonPath("$.hits[0].origin").value("SESSION"))
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(advice).contains(resolutionId).contains("phase7-cause-socket").contains("phase7-method-port");
        assertThat(advice).contains("비슷한 확정 사례");
        String self = mockMvc.perform(post("/api/v1/search/similar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"error_case_id\":\"" + caseId + "\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hits").isEmpty())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(self).contains(SimilarSearchService.EMPTY_ANSWER);
        assertThat(self).doesNotContain(resolutionId).doesNotContain(caseId);

        String none = mockMvc.perform(post("/api/v1/search/similar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"raw_log\":\"disk quota exceeded while writing the artifact\"}"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.hits").isEmpty())
                .andReturn().getResponse().getContentAsString(StandardCharsets.UTF_8);
        assertThat(none).contains(SimilarSearchService.EMPTY_ANSWER);

        mockMvc.perform(get("/api/v1/search").param("q", "phase7-cause-socket"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.items[0].kind").value("RESOLUTION"));
        mockMvc.perform(post("/api/v1/search/similar")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("{\"raw_log\":\"boom\",\"error_case_id\":\"" + caseId + "\"}"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION"));
    }
}
