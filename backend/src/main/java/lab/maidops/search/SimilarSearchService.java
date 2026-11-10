package lab.maidops.search;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import lab.maidops.api.ApiException;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.ReviewStatus;
import lab.maidops.domain.SearchKind;
import lab.maidops.errorcase.ErrorCaseEntity;
import lab.maidops.errorcase.ErrorCaseRepository;
import lab.maidops.errorcase.SecretMasker;
import lab.maidops.resolution.ResolutionEntity;
import lab.maidops.resolution.ResolutionRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class SimilarSearchService {
    public static final String EMPTY_ANSWER = "비슷한 확정 기록이 없습니다.";
    static final double THRESHOLD = 0.35;
    private static final int LIMIT = 5;
    private static final int TEXT_LIMIT = 8000;

    private final ErrorCaseRepository cases;
    private final ResolutionRepository resolutions;

    public SimilarSearchService(ErrorCaseRepository cases, ResolutionRepository resolutions) {
        this.cases = cases;
        this.resolutions = resolutions;
    }

    @Transactional(readOnly = true)
    public SimilarSearchResponse search(String rawLog, String errorCaseId) {
        boolean hasLog = rawLog != null && !rawLog.isBlank();
        boolean hasCase = errorCaseId != null && !errorCaseId.isBlank();
        if (hasLog == hasCase) {
            throw new ApiException(
                    400,
                    "VALIDATION",
                    "raw_log 또는 error_case_id 중 하나만 보내세요.",
                    "{\"raw_log\":\"Connection to localhost:5432 refused\"}");
        }
        String queryText = hasCase ? requireCase(errorCaseId).getRawText() : rawLog;
        if (queryText.length() > TEXT_LIMIT) {
            throw new ApiException(400, "VALIDATION", "비교할 로그는 8000자 이하여야 합니다.", "");
        }
        String masked = SecretMasker.mask(queryText.replace("\r\n", "\n").replace('\r', '\n'));
        double[] query = HashingCharNgramEmbedder.embed(masked);
        List<SimilarHitResponse> hits = new ArrayList<>();
        Map<String, List<ResolutionEntity>> resolutionsByCase = new HashMap<>();
        for (ResolutionEntity record : resolutions.findAllByOrderByCreatedAtAscIdAsc()) {
            resolutionsByCase.computeIfAbsent(record.getErrorCaseId(), ignored -> new ArrayList<>()).add(record);
        }
        List<ErrorCaseEntity> confirmed = cases.findByReviewStatusInOrderByCreatedAtAscIdAsc(
                List.of(ReviewStatus.APPROVED, ReviewStatus.REVISED));
        for (ErrorCaseEntity errorCase : confirmed) {
            if (hasCase && errorCase.getId().equals(errorCaseId)) {
                continue;
            }
            List<ResolutionEntity> records = resolutionsByCase.getOrDefault(errorCase.getId(), List.of());
            if (records.isEmpty()) {
                consider(hits, query, errorCase.getRawText(), SearchKind.ERROR_CASE, errorCase.getOrigin(),
                        errorCase.getId(), errorCase.getId(), errorCase.getCurrentLabel(), null, null, errorCase.getRawText());
                continue;
            }
            for (ResolutionEntity record : records) {
                String document = errorCase.getRawText() + "\n" + record.getCause() + "\n" + record.getMethod();
                consider(hits, query, document, SearchKind.RESOLUTION, record.getOrigin(), record.getId(),
                        errorCase.getId(), record.getLabel(), record.getCause(), record.getMethod(), record.getCause());
            }
        }
        hits.sort(Comparator.comparingDouble(SimilarHitResponse::similarity).reversed()
                .thenComparing(SimilarHitResponse::id));
        if (hits.size() > LIMIT) {
            hits = new ArrayList<>(hits.subList(0, LIMIT));
        }
        return new SimilarSearchResponse(
                HashingCharNgramEmbedder.EMBEDDING_ID,
                HashingCharNgramEmbedder.SIMILARITY_NOTE,
                answer(hits),
                hits);
    }

    private static void consider(
            List<SimilarHitResponse> hits,
            double[] query,
            String document,
            SearchKind kind,
            DataOrigin origin,
            String id,
            String errorCaseId,
            ErrorLabel label,
            String cause,
            String method,
            String excerptSource) {
        double similarity = HashingCharNgramEmbedder.cosine(query, HashingCharNgramEmbedder.embed(document));
        if (similarity < THRESHOLD) {
            return;
        }
        hits.add(new SimilarHitResponse(
                kind,
                origin,
                id,
                errorCaseId,
                label,
                Math.round(similarity * 10000.0) / 10000.0,
                excerpt(excerptSource),
                cause,
                method));
    }

    static String answer(List<SimilarHitResponse> hits) {
        if (hits.isEmpty()) {
            return EMPTY_ANSWER;
        }
        SimilarHitResponse top = hits.get(0);
        String cause = top.cause() == null || top.cause().isBlank() ? "원인 기록이 없습니다" : top.cause();
        String method = top.method() == null || top.method().isBlank() ? "해결 기록이 없습니다" : top.method();
        return "비슷한 확정 사례 " + hits.size() + "건. 가장 가까운 기록은 " + top.id()
                + " [" + top.origin().name() + "] 라벨 " + top.label().name()
                + " / 원인 " + cause
                + " / 해결 " + method
                + ". " + HashingCharNgramEmbedder.SIMILARITY_NOTE;
    }

    private ErrorCaseEntity requireCase(String caseId) {
        return cases.findById(caseId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "오류 사례를 찾지 못했습니다: " + caseId, "/review"));
    }

    private static String excerpt(String text) {
        String compact = text.replaceAll("\\s+", " ").trim();
        if (compact.length() <= 180) {
            return compact;
        }
        return compact.substring(0, 179) + "…";
    }
}
