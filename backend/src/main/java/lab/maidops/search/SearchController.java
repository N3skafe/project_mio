package lab.maidops.search;

import lab.maidops.api.PageResponse;
import lab.maidops.resolution.ResolutionResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class SearchController {
    private final SearchService search;

    public SearchController(SearchService search) {
        this.search = search;
    }

    @GetMapping("/search")
    public PageResponse<SearchHitResponse> search(@RequestParam("q") String query) {
        return search.search(query);
    }

    @GetMapping("/resolutions")
    public PageResponse<ResolutionResponse> resolutions(@RequestParam(value = "q", required = false) String query) {
        if (query == null || query.isBlank()) {
            return search.listResolutions();
        }
        return search.resolutions(query);
    }
}
