package lab.maidops.resolution;

import java.time.Instant;

import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;

public record ResolutionResponse(
        String id,
        String errorCaseId,
        String projectId,
        ErrorLabel label,
        String cause,
        String method,
        DataOrigin origin,
        Instant createdAt) {
    public static ResolutionResponse from(ResolutionEntity entity) {
        return new ResolutionResponse(
                entity.getId(),
                entity.getErrorCaseId(),
                entity.getProjectId(),
                entity.getLabel(),
                entity.getCause(),
                entity.getMethod(),
                entity.getOrigin(),
                entity.getCreatedAt());
    }
}
