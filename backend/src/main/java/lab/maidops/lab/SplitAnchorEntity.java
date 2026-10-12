package lab.maidops.lab;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lab.maidops.domain.DatasetSplit;

@Entity
@Table(name = "dataset_split_anchors")
public class SplitAnchorEntity {
    @Id
    @Column(name = "template_hash", length = 64)
    private String templateHash;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private DatasetSplit split;

    @Column(name = "policy_version", nullable = false, length = 64)
    private String policyVersion;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public String getTemplateHash() {
        return templateHash;
    }

    public void setTemplateHash(String templateHash) {
        this.templateHash = templateHash;
    }

    public DatasetSplit getSplit() {
        return split;
    }

    public void setSplit(DatasetSplit split) {
        this.split = split;
    }

    public String getPolicyVersion() {
        return policyVersion;
    }

    public void setPolicyVersion(String policyVersion) {
        this.policyVersion = policyVersion;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }
}
