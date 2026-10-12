package lab.maidops.lab;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lab.maidops.domain.DatasetSplit;
import lab.maidops.domain.ErrorLabel;

@Entity
@Table(name = "training_examples")
public class TrainingExampleEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "training_run_id", nullable = false, length = 64)
    private String trainingRunId;

    @Column(name = "error_case_id", nullable = false, length = 64)
    private String errorCaseId;

    @Column(name = "group_key", nullable = false, length = 64)
    private String groupKey;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 16)
    private DatasetSplit split;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 64)
    private ErrorLabel label;

    @Column(name = "template_hash", nullable = false, length = 64)
    private String templateHash;

    @Column(name = "text_sha256", nullable = false, length = 64)
    private String textSha256;

    public Long getId() {
        return id;
    }

    public String getTrainingRunId() {
        return trainingRunId;
    }

    public void setTrainingRunId(String trainingRunId) {
        this.trainingRunId = trainingRunId;
    }

    public String getErrorCaseId() {
        return errorCaseId;
    }

    public void setErrorCaseId(String errorCaseId) {
        this.errorCaseId = errorCaseId;
    }

    public String getGroupKey() {
        return groupKey;
    }

    public void setGroupKey(String groupKey) {
        this.groupKey = groupKey;
    }

    public DatasetSplit getSplit() {
        return split;
    }

    public void setSplit(DatasetSplit split) {
        this.split = split;
    }

    public ErrorLabel getLabel() {
        return label;
    }

    public void setLabel(ErrorLabel label) {
        this.label = label;
    }

    public String getTemplateHash() {
        return templateHash;
    }

    public void setTemplateHash(String templateHash) {
        this.templateHash = templateHash;
    }

    public String getTextSha256() {
        return textSha256;
    }

    public void setTextSha256(String textSha256) {
        this.textSha256 = textSha256;
    }
}
