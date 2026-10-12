package lab.maidops.lab;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lab.maidops.domain.TrainingStatus;

@Entity
@Table(name = "training_runs")
public class TrainingRunEntity {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private TrainingStatus status;

    @Column(name = "dataset_fingerprint", nullable = false, length = 64)
    private String datasetFingerprint;

    @Column(name = "label_schema_version", nullable = false, length = 64)
    private String labelSchemaVersion;

    @Column(name = "embedding_id", nullable = false, length = 120)
    private String embeddingId;

    @Column(name = "split_policy", nullable = false, length = 64)
    private String splitPolicy;

    @Column(name = "config_json")
    private String configJson;

    @Column(name = "metrics_json")
    private String metricsJson;

    @Column(name = "code_version", length = 80)
    private String codeVersion;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Column(name = "error_message", length = 2000)
    private String errorMessage;

    @Column(name = "claimed_by", length = 64)
    private String claimedBy;

    @Column(name = "lease_expires_at")
    private Instant leaseExpiresAt;

    @Column(name = "reserved_model_id", length = 64)
    private String reservedModelId;

    @Column(name = "cancel_requested_at")
    private Instant cancelRequestedAt;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public TrainingStatus getStatus() {
        return status;
    }

    public void setStatus(TrainingStatus status) {
        this.status = status;
    }

    public String getDatasetFingerprint() {
        return datasetFingerprint;
    }

    public void setDatasetFingerprint(String datasetFingerprint) {
        this.datasetFingerprint = datasetFingerprint;
    }

    public String getLabelSchemaVersion() {
        return labelSchemaVersion;
    }

    public void setLabelSchemaVersion(String labelSchemaVersion) {
        this.labelSchemaVersion = labelSchemaVersion;
    }

    public String getEmbeddingId() {
        return embeddingId;
    }

    public void setEmbeddingId(String embeddingId) {
        this.embeddingId = embeddingId;
    }

    public String getSplitPolicy() {
        return splitPolicy;
    }

    public void setSplitPolicy(String splitPolicy) {
        this.splitPolicy = splitPolicy;
    }

    public String getConfigJson() {
        return configJson;
    }

    public void setConfigJson(String configJson) {
        this.configJson = configJson;
    }

    public String getMetricsJson() {
        return metricsJson;
    }

    public void setMetricsJson(String metricsJson) {
        this.metricsJson = metricsJson;
    }

    public String getCodeVersion() {
        return codeVersion;
    }

    public void setCodeVersion(String codeVersion) {
        this.codeVersion = codeVersion;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(Instant startedAt) {
        this.startedAt = startedAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(Instant finishedAt) {
        this.finishedAt = finishedAt;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public void setErrorMessage(String errorMessage) {
        this.errorMessage = errorMessage;
    }

    public String getClaimedBy() {
        return claimedBy;
    }

    public void setClaimedBy(String claimedBy) {
        this.claimedBy = claimedBy;
    }

    public Instant getLeaseExpiresAt() {
        return leaseExpiresAt;
    }

    public void setLeaseExpiresAt(Instant leaseExpiresAt) {
        this.leaseExpiresAt = leaseExpiresAt;
    }

    public String getReservedModelId() {
        return reservedModelId;
    }

    public void setReservedModelId(String reservedModelId) {
        this.reservedModelId = reservedModelId;
    }

    public Instant getCancelRequestedAt() {
        return cancelRequestedAt;
    }

    public void setCancelRequestedAt(Instant cancelRequestedAt) {
        this.cancelRequestedAt = cancelRequestedAt;
    }
}
