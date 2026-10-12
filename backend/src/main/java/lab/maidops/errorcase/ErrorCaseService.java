package lab.maidops.errorcase;

import java.time.Instant;
import java.util.List;

import lab.maidops.api.ApiException;
import lab.maidops.api.CursorCodec;
import lab.maidops.api.PageResponse;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.InferenceState;
import lab.maidops.domain.LabelSource;
import lab.maidops.domain.ReviewDecision;
import lab.maidops.domain.ReviewStatus;
import lab.maidops.job.IdAllocator;
import lab.maidops.resolution.ResolutionEntity;
import lab.maidops.resolution.ResolutionRepository;
import lab.maidops.resolution.ResolutionResponse;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ErrorCaseService {
    private final ErrorCaseRepository cases;
    private final ResolutionRepository resolutions;
    private final IdAllocator ids;

    public ErrorCaseService(
            ErrorCaseRepository cases,
            ResolutionRepository resolutions,
            IdAllocator ids) {
        this.cases = cases;
        this.resolutions = resolutions;
        this.ids = ids;
    }

    @Transactional(readOnly = true)
    public PageResponse<ErrorCaseResponse> list(String cursor, Integer limit) {
        int pageSize = pageSize(limit);
        CursorCodec.Cursor position = CursorCodec.decode(cursor);
        List<ErrorCaseEntity> rows = position == null
                ? cases.firstPage(pageSize + 1)
                : cases.pageAfter(position.createdAt(), position.id(), pageSize + 1);
        boolean more = rows.size() > pageSize;
        List<ErrorCaseEntity> page = more ? rows.subList(0, pageSize) : rows;
        String next = null;
        if (more && !page.isEmpty()) {
            ErrorCaseEntity last = page.get(page.size() - 1);
            next = CursorCodec.encode(last.getCreatedAt(), last.getId());
        }
        return new PageResponse<>(page.stream().map(ErrorCaseResponse::from).toList(), next);
    }

    @Transactional(readOnly = true)
    public PageResponse<ErrorCaseResponse> confirmed() {
        List<ErrorCaseResponse> items = cases
                .findByReviewStatusInOrderByCreatedAtAscIdAsc(List.of(ReviewStatus.APPROVED, ReviewStatus.REVISED))
                .stream()
                .map(ErrorCaseResponse::from)
                .toList();
        return new PageResponse<>(items, null);
    }

    @Transactional(readOnly = true)
    public ErrorCaseResponse get(String caseId) {
        return ErrorCaseResponse.from(require(caseId));
    }

    @Transactional
    public ErrorCaseResponse review(String caseId, ReviewDecision decision, ErrorLabel label) {
        ErrorCaseEntity errorCase = require(caseId);
        String note = apply(errorCase, decision, label);
        errorCase.addRevision(LabelRevisionEntity.create(
                errorCase.getCurrentLabel(),
                errorCase.getReviewStatus(),
                LabelSource.USER,
                note,
                Instant.now()));
        return ErrorCaseResponse.from(errorCase);
    }

    @Transactional
    public ResolutionResponse saveResolution(String caseId, String cause, String method) {
        String causeText = requiredText(cause, "원인");
        String methodText = requiredText(method, "해결 방법");
        ErrorCaseEntity errorCase = require(caseId);
        if (errorCase.getReviewStatus() != ReviewStatus.APPROVED
                && errorCase.getReviewStatus() != ReviewStatus.REVISED) {
            throw new ApiException(
                    409,
                    "STATE",
                    "승인 또는 수정된 사례만 해결 기록으로 저장할 수 있습니다. 보류와 초안은 제외됩니다.",
                    "라벨을 승인하거나 수정한 뒤 저장하세요.");
        }
        ResolutionEntity record = resolutions.save(ResolutionEntity.create(
                ids.nextResolutionId(),
                errorCase.getId(),
                errorCase.getProjectId(),
                errorCase.getCurrentLabel(),
                causeText,
                methodText,
                DataOrigin.SESSION,
                Instant.now()));
        return ResolutionResponse.from(record);
    }

    private String apply(ErrorCaseEntity errorCase, ReviewDecision decision, ErrorLabel label) {
        if (errorCase.getInferenceState() == InferenceState.PENDING || errorCase.getCurrentLabel() == null) {
            throw new ApiException(
                    409,
                    "STATE",
                    "모델 초안이 아직 없습니다. 승인, 수정, 보류를 하지 않습니다.",
                    "초안이 도착한 뒤 검토하세요.");
        }
        if (decision == ReviewDecision.APPROVE) {
            errorCase.setReviewStatus(ReviewStatus.APPROVED);
            return "사용자가 초안 라벨을 승인했습니다. 학습은 시작하지 않습니다.";
        }
        if (decision == ReviewDecision.DEFER) {
            errorCase.setReviewStatus(ReviewStatus.DEFERRED);
            return "사용자가 검토를 보류했습니다. 학습 정답에서 제외됩니다.";
        }
        if (decision == ReviewDecision.REVISE) {
            if (label == null || label == errorCase.getCurrentLabel()) {
                throw new ApiException(400, "VALIDATION", "수정하려면 현재와 다른 라벨을 선택하세요.", "OTHER");
            }
            errorCase.setCurrentLabel(label);
            errorCase.setReviewStatus(ReviewStatus.REVISED);
            return "사용자가 라벨을 수정했습니다. 학습은 시작하지 않습니다.";
        }
        throw new ApiException(400, "VALIDATION", "지원하지 않는 검토 결정입니다.", "");
    }

    private ErrorCaseEntity require(String caseId) {
        return cases.findById(caseId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "오류 사례를 찾지 못했습니다: " + caseId, "/review"));
    }

    private static String requiredText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new ApiException(400, "VALIDATION", name + "을 입력하세요.", "");
        }
        String trimmed = value.trim();
        if (trimmed.length() > 500) {
            throw new ApiException(400, "VALIDATION", name + "은 500자 이하여야 합니다.", "");
        }
        return trimmed;
    }

    private static int pageSize(Integer limit) {
        int resolved = limit == null ? 50 : limit;
        if (resolved < 1 || resolved > 100) {
            throw new ApiException(400, "VALIDATION", "limit은 1 이상 100 이하여야 합니다.", "50");
        }
        return resolved;
    }
}
