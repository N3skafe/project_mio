package lab.maidops.lab;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "model_versions")
public class ModelVersionEntity {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "training_run_id", nullable = false, length = 64)
    private String trainingRunId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "embedding_id", nullable = false, length = 120)
    private String embeddingId;

    @Column(name = "label_schema_version", nullable = false, length = 64)
    private String labelSchemaVersion;

    @Column(name = "dataset_fingerprint", nullable = false, length = 64)
    private String datasetFingerprint;

    @Column(name = "code_version", nullable = false, length = 80)
    private String codeVersion;

    @Column(nullable = false, length = 16)
    private String device;

    @Column(nullable = false)
    private int seed;

    @Column(name = "config_json", nullable = false)
    private String configJson;

    @Column(name = "metrics_json", nullable = false)
    private String metricsJson;

    @Column(name = "model_file", nullable = false, length = 120)
    private String modelFile;

    @Column(name = "checksum_sha256", nullable = false, length = 64)
    private String checksumSha256;

    @Column(name = "byte_size", nullable = false)
    private long byteSize;

    @Column(name = "is_default", nullable = false)
    private boolean defaultModel;

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getTrainingRunId() {
        return trainingRunId;
    }

    public void setTrainingRunId(String trainingRunId) {
        this.trainingRunId = trainingRunId;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public String getEmbeddingId() {
        return embeddingId;
    }

    public void setEmbeddingId(String embeddingId) {
        this.embeddingId = embeddingId;
    }

    public String getLabelSchemaVersion() {
        return labelSchemaVersion;
    }

    public void setLabelSchemaVersion(String labelSchemaVersion) {
        this.labelSchemaVersion = labelSchemaVersion;
    }

    public String getDatasetFingerprint() {
        return datasetFingerprint;
    }

    public void setDatasetFingerprint(String datasetFingerprint) {
        this.datasetFingerprint = datasetFingerprint;
    }

    public String getCodeVersion() {
        return codeVersion;
    }

    public void setCodeVersion(String codeVersion) {
        this.codeVersion = codeVersion;
    }

    public String getDevice() {
        return device;
    }

    public void setDevice(String device) {
        this.device = device;
    }

    public int getSeed() {
        return seed;
    }

    public void setSeed(int seed) {
        this.seed = seed;
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

    public String getModelFile() {
        return modelFile;
    }

    public void setModelFile(String modelFile) {
        this.modelFile = modelFile;
    }

    public String getChecksumSha256() {
        return checksumSha256;
    }

    public void setChecksumSha256(String checksumSha256) {
        this.checksumSha256 = checksumSha256;
    }

    public long getByteSize() {
        return byteSize;
    }

    public void setByteSize(long byteSize) {
        this.byteSize = byteSize;
    }

    public boolean isDefaultModel() {
        return defaultModel;
    }

    public void setDefaultModel(boolean defaultModel) {
        this.defaultModel = defaultModel;
    }
}
