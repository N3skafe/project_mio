package lab.maidops.search;

import com.fasterxml.jackson.annotation.JsonInclude;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.SearchKind;

public record SimilarHitResponse(
        SearchKind kind,
        DataOrigin origin,
        String id,
        String errorCaseId,
        ErrorLabel label,
        double similarity,
        String excerpt,
        @JsonInclude(JsonInclude.Include.ALWAYS) String cause,
        @JsonInclude(JsonInclude.Include.ALWAYS) String method) {
}
