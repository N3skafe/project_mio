package lab.maidops.worker;

import java.util.List;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lab.maidops.api.ApiException;
import lab.maidops.job.JobResponse;
import lab.maidops.worker.WorkerJobService.ClaimedJob;
import lab.maidops.worker.WorkerJobService.FinishRequest;
import lab.maidops.worker.WorkerJobService.OutputLine;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/worker")
public class WorkerController {
    private static final TypeReference<List<OutputLine>> LINES = new TypeReference<>() {
    };

    private final WorkerJobService workers;
    private final ObjectMapper objectMapper;

    public WorkerController(WorkerJobService workers, ObjectMapper objectMapper) {
        this.workers = workers;
        this.objectMapper = objectMapper;
    }

    @PostMapping("/heartbeat")
    public void heartbeat(@RequestHeader("X-Worker-Id") String workerId) {
        workers.heartbeat(workerId);
    }

    @PostMapping("/claim")
    public ResponseEntity<ClaimedJob> claim(@RequestHeader("X-Worker-Id") String workerId) {
        return workers.claim(workerId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @PostMapping("/jobs/{id}/heartbeat")
    public void heartbeatJob(@RequestHeader("X-Worker-Id") String workerId, @PathVariable String id) {
        workers.heartbeatJob(workerId, id);
    }

    @PostMapping("/jobs/{id}/events")
    public ResponseEntity<Void> events(
            @RequestHeader("X-Worker-Id") String workerId,
            @PathVariable String id,
            @RequestBody JsonNode body) {
        if (body == null || body.isNull()) {
            throw new ApiException(400, "VALIDATION", "로그 본문이 없습니다.", "");
        }
        if (body.isArray()) {
            workers.appendOutput(workerId, id, objectMapper.convertValue(body, LINES));
            return ResponseEntity.noContent().build();
        }
        if (!body.isObject()) {
            throw new ApiException(400, "VALIDATION", "로그 배치는 객체여야 합니다.", "");
        }
        String batchId = textOrNull(body.get("batch_id"));
        workers.appendBatch(workerId, id, batchId, objectMapper.convertValue(body.path("lines"), LINES));
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/jobs/{id}/finish")
    public JobResponse finish(
            @RequestHeader("X-Worker-Id") String workerId,
            @PathVariable String id,
            @RequestBody FinishRequest request) {
        return workers.finish(workerId, id, request);
    }

    private static String textOrNull(JsonNode node) {
        if (node == null || node.isNull()) {
            return null;
        }
        String text = node.asText();
        return text.isBlank() ? null : text;
    }
}
