package lab.maidops.worker;

import java.util.List;

import lab.maidops.job.JobResponse;
import lab.maidops.worker.WorkerJobService.ClaimedJob;
import lab.maidops.worker.WorkerJobService.FinishRequest;
import lab.maidops.worker.WorkerJobService.OutputLine;
import org.springframework.http.HttpStatus;
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
    private final WorkerJobService workers;

    public WorkerController(WorkerJobService workers) {
        this.workers = workers;
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
    public void events(
            @RequestHeader("X-Worker-Id") String workerId,
            @PathVariable String id,
            @RequestBody List<OutputLine> lines) {
        workers.appendOutput(workerId, id, lines);
    }

    @PostMapping("/jobs/{id}/finish")
    public JobResponse finish(
            @RequestHeader("X-Worker-Id") String workerId,
            @PathVariable String id,
            @RequestBody FinishRequest request) {
        return workers.finish(workerId, id, request);
    }
}
