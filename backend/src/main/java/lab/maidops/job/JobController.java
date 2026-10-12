package lab.maidops.job;

import lab.maidops.api.PageResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import jakarta.validation.Valid;

@RestController
@RequestMapping("/api/v1/jobs")
public class JobController {
    private final JobService jobs;

    public JobController(JobService jobs) {
        this.jobs = jobs;
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public JobResponse create(
            @Valid @RequestBody CreateJobRequest request,
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey) {
        return jobs.create(request.projectId(), request.taskId(), idempotencyKey);
    }

    @GetMapping
    public PageResponse<JobResponse> list(
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return jobs.list(cursor, limit);
    }

    @GetMapping("/{id}")
    public JobResponse get(@PathVariable String id) {
        return jobs.get(id);
    }

    @GetMapping("/{id}/events")
    public PageResponse<JobEventResponse> events(
            @PathVariable String id,
            @RequestParam(required = false) Integer after) {
        return jobs.events(id, after);
    }

    @PostMapping("/{id}/cancel")
    public JobResponse cancel(@PathVariable String id) {
        return jobs.cancel(id);
    }
}
