package lab.maidops.job;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

@Entity
@Table(name = "idempotency_keys")
public class IdempotencyKeyEntity {
    @Id
    @Column(name = "key_text", length = 128)
    private String keyText;

    @Column(name = "request_hash", nullable = false, length = 64)
    private String requestHash;

    @Column(name = "job_id", length = 64)
    private String jobId;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public static IdempotencyKeyEntity reserve(String keyText, String requestHash, Instant createdAt) {
        IdempotencyKeyEntity entity = new IdempotencyKeyEntity();
        entity.keyText = keyText;
        entity.requestHash = requestHash;
        entity.createdAt = createdAt;
        return entity;
    }

    public String getRequestHash() {
        return requestHash;
    }

    public String getJobId() {
        return jobId;
    }

    public void setJobId(String jobId) {
        this.jobId = jobId;
    }
}
