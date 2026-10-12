package lab.maidops.errorcase;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.InferenceState;
import lab.maidops.domain.LabelSource;
import lab.maidops.domain.ReviewStatus;

@Entity
@Table(name = "error_cases")
public class ErrorCaseEntity {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "job_id", nullable = false, length = 64)
    private String jobId;

    @Column(name = "project_id", nullable = false, length = 64)
    private String projectId;

    @Column(name = "raw_text", nullable = false, length = 8000)
    private String rawText;

    @Enumerated(EnumType.STRING)
    @Column(name = "draft_label", length = 64)
    private ErrorLabel draftLabel;

    @Enumerated(EnumType.STRING)
    @Column(name = "draft_source", nullable = false, length = 32)
    private LabelSource draftSource;

    @Enumerated(EnumType.STRING)
    @Column(name = "current_label", length = 64)
    private ErrorLabel currentLabel;

    @Enumerated(EnumType.STRING)
    @Column(name = "review_status", nullable = false, length = 32)
    private ReviewStatus reviewStatus;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private DataOrigin origin;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "rule_version", length = 64)
    private String ruleVersion;

    @Column(name = "matched_keyword", length = 120)
    private String matchedKeyword;

    @Enumerated(EnumType.STRING)
    @Column(name = "inference_state", nullable = false, length = 16)
    private InferenceState inferenceState = InferenceState.READY;

    @Column(name = "model_version_id", length = 64)
    private String modelVersionId;

    @OneToMany(mappedBy = "errorCase", cascade = CascadeType.ALL, orphanRemoval = true)
    @OrderBy("createdAt asc, id asc")
    private List<LabelRevisionEntity> revisions = new ArrayList<>();

    public String getId() {
        return id;
    }

    public void setId(String id) {
        this.id = id;
    }

    public String getJobId() {
        return jobId;
    }

    public void setJobId(String jobId) {
        this.jobId = jobId;
    }

    public String getProjectId() {
        return projectId;
    }

    public void setProjectId(String projectId) {
        this.projectId = projectId;
    }

    public String getRawText() {
        return rawText;
    }

    public void setRawText(String rawText) {
        this.rawText = rawText;
    }

    public ErrorLabel getDraftLabel() {
        return draftLabel;
    }

    public void setDraftLabel(ErrorLabel draftLabel) {
        this.draftLabel = draftLabel;
    }

    public LabelSource getDraftSource() {
        return draftSource;
    }

    public void setDraftSource(LabelSource draftSource) {
        this.draftSource = draftSource;
    }

    public ErrorLabel getCurrentLabel() {
        return currentLabel;
    }

    public void setCurrentLabel(ErrorLabel currentLabel) {
        this.currentLabel = currentLabel;
    }

    public ReviewStatus getReviewStatus() {
        return reviewStatus;
    }

    public void setReviewStatus(ReviewStatus reviewStatus) {
        this.reviewStatus = reviewStatus;
    }

    public DataOrigin getOrigin() {
        return origin;
    }

    public void setOrigin(DataOrigin origin) {
        this.origin = origin;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(Instant createdAt) {
        this.createdAt = createdAt;
    }

    public String getRuleVersion() {
        return ruleVersion;
    }

    public void setRuleVersion(String ruleVersion) {
        this.ruleVersion = ruleVersion;
    }

    public String getMatchedKeyword() {
        return matchedKeyword;
    }

    public void setMatchedKeyword(String matchedKeyword) {
        this.matchedKeyword = matchedKeyword;
    }

    public InferenceState getInferenceState() {
        return inferenceState;
    }

    public void setInferenceState(InferenceState inferenceState) {
        this.inferenceState = inferenceState;
    }

    public String getModelVersionId() {
        return modelVersionId;
    }

    public void setModelVersionId(String modelVersionId) {
        this.modelVersionId = modelVersionId;
    }

    public List<LabelRevisionEntity> getRevisions() {
        return revisions;
    }

    public void addRevision(LabelRevisionEntity revision) {
        revision.setErrorCase(this);
        revisions.add(revision);
    }
}
