package lab.maidops.search;

import java.util.ArrayList;
import java.util.List;

import lab.maidops.api.ApiException;
import lab.maidops.api.PageResponse;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.SearchKind;
import lab.maidops.errorcase.ErrorCaseRepository;
import lab.maidops.job.JobEventRepository;
import lab.maidops.job.JobRepository;
import lab.maidops.resolution.ResolutionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SearchService {
    private final JobRepository jobs;
    private final JobEventRepository events;
    private final ErrorCaseRepository cases;
    private final ResolutionRepository resolutions;

    public SearchService(
            JobRepository jobs,
            JobEventRepository events,
            ErrorCaseRepository cases,
            ResolutionRepository resolutions) {
        this.jobs = jobs;
        this.events = events;
        this.cases = cases;
        this.resolutions = resolutions;
    }

    @Transactional(readOnly = true)
    public PageResponse<SearchHitResponse> search(String query) {
        String keyword = requiredQuery(query);
        String pattern = likePattern(keyword);
        List<SearchHitResponse> hits = new ArrayList<>();
        jobs.search(pattern).forEach(job -> hits.add(jobHit(job)));
        events.searchJobsByText(pattern).stream()
                .filter(job -> hits.stream().noneMatch(hit -> hit.title().startsWith(job.getId() + " ")))
                .forEach(job -> hits.add(jobHit(job)));
        cases.search(pattern).forEach(errorCase -> hits.add(new SearchHitResponse(
                SearchKind.ERROR_CASE,
                errorCase.getOrigin(),
                errorCase.getId() + " " + errorCase.getDraftSource().name() + " "
                        + errorCase.getReviewStatus().name() + " "
                        + (errorCase.getDraftLabel() == null ? "대기" : errorCase.getDraftLabel().name()),
                excerpt(errorCase.getRawText()))));
        resolutions.search(pattern).forEach(record -> hits.add(new SearchHitResponse(
                SearchKind.RESOLUTION,
                record.getOrigin(),
                record.getId() + " " + record.getLabel().name(),
                excerpt(record.getCause() + " " + record.getMethod()))));
        return new PageResponse<>(hits, null);
    }

    private static SearchHitResponse jobHit(lab.maidops.job.JobEntity job) {
        return new SearchHitResponse(
                SearchKind.JOB,
                DataOrigin.SESSION,
                job.getId() + " " + job.getStatus().name(),
                "project=" + job.getProjectId() + " task=" + job.getTaskId());
    }

    @Transactional(readOnly = true)
    public PageResponse<lab.maidops.resolution.ResolutionResponse> listResolutions() {
        List<lab.maidops.resolution.ResolutionResponse> items = resolutions.findAllByOrderByCreatedAtAscIdAsc().stream()
                .map(lab.maidops.resolution.ResolutionResponse::from)
                .toList();
        return new PageResponse<>(items, null);
    }

    @Transactional(readOnly = true)
    public PageResponse<lab.maidops.resolution.ResolutionResponse> resolutions(String query) {
        String pattern = likePattern(requiredQuery(query));
        List<lab.maidops.resolution.ResolutionResponse> items = resolutions.search(pattern).stream()
                .map(lab.maidops.resolution.ResolutionResponse::from)
                .toList();
        return new PageResponse<>(items, null);
    }

    private static String requiredQuery(String query) {
        if (query == null || query.isBlank()) {
            throw new ApiException(400, "VALIDATION", "검색어가 비어 있습니다.", "postgres");
        }
        String trimmed = query.trim();
        if (trimmed.length() > 200) {
            throw new ApiException(400, "VALIDATION", "검색어는 200자 이하여야 합니다.", "");
        }
        return trimmed;
    }

    static String likePattern(String query) {
        return query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_");
    }

    private static String excerpt(String text) {
        String compact = text.replaceAll("\\s+", " ").trim();
        if (compact.length() <= 180) {
            return compact;
        }
        return compact.substring(0, 179) + "…";
    }
}
