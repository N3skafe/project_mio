package lab.maidops.resolution;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;

@Entity
@Table(name = "resolution_records")
public class ResolutionEntity {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "error_case_id", nullable = false, length = 64)
    private String errorCaseId;

    @Column(name = "project_id", nullable = false, length = 64)
    private String projectId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 64)
    private ErrorLabel label;

    @Column(nullable = false, length = 500)
    private String cause;

    @Column(nullable = false, length = 500)
    private String method;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private DataOrigin origin;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public static ResolutionEntity create(
            String id,
            String errorCaseId,
            String projectId,
            ErrorLabel label,
            String cause,
            String method,
            DataOrigin origin,
            Instant createdAt) {
        ResolutionEntity entity = new ResolutionEntity();
        entity.id = id;
        entity.errorCaseId = errorCaseId;
        entity.projectId = projectId;
        entity.label = label;
        entity.cause = cause;
        entity.method = method;
        entity.origin = origin;
        entity.createdAt = createdAt;
        return entity;
    }

    public String getId() {
        return id;
    }

    public String getErrorCaseId() {
        return errorCaseId;
    }

    public String getProjectId() {
        return projectId;
    }

    public ErrorLabel getLabel() {
        return label;
    }

    public String getCause() {
        return cause;
    }

    public String getMethod() {
        return method;
    }

    public DataOrigin getOrigin() {
        return origin;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
