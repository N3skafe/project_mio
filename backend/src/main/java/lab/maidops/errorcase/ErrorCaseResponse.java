package lab.maidops.errorcase;

import java.time.Instant;
import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.InferenceState;
import lab.maidops.domain.LabelSource;
import lab.maidops.domain.ReviewStatus;

public record ErrorCaseResponse(
        String id,
        String jobId,
        String projectId,
        String rawText,
        ErrorLabel draftLabel,
        LabelSource draftSource,
        ErrorLabel currentLabel,
        ReviewStatus reviewStatus,
        DataOrigin origin,
        @JsonInclude(JsonInclude.Include.ALWAYS) String ruleVersion,
        @JsonInclude(JsonInclude.Include.ALWAYS) String matchedKeyword,
        @JsonInclude(JsonInclude.Include.ALWAYS) ErrorLabel confirmedLabel,
        InferenceState inferenceState,
        @JsonInclude(JsonInclude.Include.ALWAYS) String modelVersionId,
        Instant createdAt,
        List<RevisionResponse> revisions) {
    public static ErrorCaseResponse from(ErrorCaseEntity entity) {
        boolean confirmed = entity.getReviewStatus() == ReviewStatus.APPROVED
                || entity.getReviewStatus() == ReviewStatus.REVISED;
        return new ErrorCaseResponse(
                entity.getId(),
                entity.getJobId(),
                entity.getProjectId(),
                entity.getRawText(),
                entity.getDraftLabel(),
                entity.getDraftSource(),
                entity.getCurrentLabel(),
                entity.getReviewStatus(),
                entity.getOrigin(),
                entity.getRuleVersion(),
                entity.getMatchedKeyword(),
                confirmed ? entity.getCurrentLabel() : null,
                entity.getInferenceState(),
                entity.getModelVersionId(),
                entity.getCreatedAt(),
                entity.getRevisions().stream().map(RevisionResponse::from).toList());
    }
}

record RevisionResponse(
        ErrorLabel label,
        ReviewStatus reviewStatus,
        LabelSource source,
        String note,
        Instant createdAt) {
    static RevisionResponse from(LabelRevisionEntity entity) {
        return new RevisionResponse(
                entity.getLabel(),
                entity.getReviewStatus(),
                entity.getSource(),
                entity.getNote(),
                entity.getCreatedAt());
    }
}
