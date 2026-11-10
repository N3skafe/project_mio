package lab.maidops.search;

import lab.maidops.api.PageResponse;
import lab.maidops.resolution.ResolutionResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class SearchController {
    private final SearchService search;
    private final SimilarSearchService similar;

    public SearchController(SearchService search, SimilarSearchService similar) {
        this.search = search;
        this.similar = similar;
    }

    @GetMapping("/search")
    public PageResponse<SearchHitResponse> search(@RequestParam("q") String query) {
        return search.search(query);
    }

    @PostMapping("/search/similar")
    public SimilarSearchResponse similar(@RequestBody SimilarSearchRequest request) {
        if (request == null) {
            request = new SimilarSearchRequest(null, null);
        }
        return similar.search(request.rawLog(), request.errorCaseId());
    }

    @GetMapping("/resolutions")
    public PageResponse<ResolutionResponse> resolutions(@RequestParam(value = "q", required = false) String query) {
        if (query == null || query.isBlank()) {
            return search.listResolutions();
        }
        return search.resolutions(query);
    }
}
