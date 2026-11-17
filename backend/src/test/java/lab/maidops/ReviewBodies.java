package lab.maidops;

import java.nio.charset.StandardCharsets;

import com.jayway.jsonpath.JsonPath;
import org.springframework.test.web.servlet.MockMvc;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

final class ReviewBodies {
    private ReviewBodies() {
    }

    static String json(MockMvc mockMvc, String caseId, String decision, String label) throws Exception {
        String current = mockMvc.perform(get("/api/v1/error-cases/" + caseId))
                .andReturn()
                .getResponse()
                .getContentAsString(StandardCharsets.UTF_8);
        Number revision = JsonPath.read(current, "$.latest_revision_id");
        if (revision == null) {
            throw new IllegalStateException("latest_revision_id is null for " + caseId);
        }
        if (label == null) {
            return "{\"decision\":\"" + decision + "\",\"expected_revision\":" + revision.longValue() + "}";
        }
        return "{\"decision\":\"" + decision + "\",\"label\":\"" + label
                + "\",\"expected_revision\":" + revision.longValue() + "}";
    }
}
