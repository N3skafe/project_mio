package lab.maidops.errorcase;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.LabelSource;
import lab.maidops.domain.ReviewStatus;

@Entity
@Table(name = "label_revisions")
public class LabelRevisionEntity {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "error_case_id", nullable = false)
    private ErrorCaseEntity errorCase;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 64)
    private ErrorLabel label;

    @Enumerated(EnumType.STRING)
    @Column(name = "review_status", nullable = false, length = 32)
    private ReviewStatus reviewStatus;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private LabelSource source;

    @Column(nullable = false, length = 1000)
    private String note;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    public static LabelRevisionEntity create(
            ErrorLabel label,
            ReviewStatus reviewStatus,
            LabelSource source,
            String note,
            Instant createdAt) {
        LabelRevisionEntity revision = new LabelRevisionEntity();
        revision.label = label;
        revision.reviewStatus = reviewStatus;
        revision.source = source;
        revision.note = note;
        revision.createdAt = createdAt;
        return revision;
    }

    public void setErrorCase(ErrorCaseEntity errorCase) {
        this.errorCase = errorCase;
    }

    public ErrorLabel getLabel() {
        return label;
    }

    public ReviewStatus getReviewStatus() {
        return reviewStatus;
    }

    public LabelSource getSource() {
        return source;
    }

    public String getNote() {
        return note;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }
}
