package lab.maidops.errorcase;

import lab.maidops.api.PageResponse;
import lab.maidops.lab.ModelDraftService;
import lab.maidops.resolution.ResolutionRequest;
import lab.maidops.resolution.ResolutionResponse;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/error-cases")
public class ErrorCaseController {
    private final ErrorCaseService cases;
    private final ModelDraftService drafts;

    public ErrorCaseController(ErrorCaseService cases, ModelDraftService drafts) {
        this.cases = cases;
        this.drafts = drafts;
    }

    @GetMapping
    public PageResponse<ErrorCaseResponse> list(
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return cases.list(cursor, limit);
    }

    @GetMapping("/confirmed")
    public PageResponse<ErrorCaseResponse> confirmed() {
        return cases.confirmed();
    }

    @PostMapping("/import")
    @ResponseStatus(HttpStatus.CREATED)
    public ErrorCaseResponse importLog(@RequestBody ImportLogRequest request) {
        if (request == null) {
            request = new ImportLogRequest(null, null, null, null, null);
        }
        return ErrorCaseResponse.from(drafts.importLog(
                request.projectId(),
                request.rawLog(),
                request.lines(),
                request.sourceHint(),
                request.title()));
    }

    @GetMapping("/{id}")
    public ErrorCaseResponse get(@PathVariable String id) {
        return cases.get(id);
    }

    @PostMapping("/{id}/reviews")
    public ErrorCaseResponse review(@PathVariable String id, @Valid @RequestBody ReviewRequest request) {
        return cases.review(id, request.decision(), request.label());
    }

    @PostMapping("/{id}/resolutions")
    public ResolutionResponse saveResolution(
            @PathVariable String id,
            @Valid @RequestBody ResolutionRequest request) {
        return cases.saveResolution(id, request.cause(), request.method());
    }
}
