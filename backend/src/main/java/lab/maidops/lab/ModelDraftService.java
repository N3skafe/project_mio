package lab.maidops.lab;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Optional;

import jakarta.validation.constraints.NotNull;

import jakarta.annotation.PostConstruct;
import lab.maidops.api.ApiException;
import lab.maidops.domain.DataOrigin;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.InferenceState;
import lab.maidops.domain.LabelSource;
import lab.maidops.domain.ReviewStatus;
import lab.maidops.errorcase.ErrorCaseEntity;
import lab.maidops.errorcase.ErrorCaseRepository;
import lab.maidops.errorcase.FailureRuleClassifier;
import lab.maidops.errorcase.FailureRuleClassifier.RuleDraft;
import lab.maidops.errorcase.LabelRevisionEntity;
import lab.maidops.job.IdAllocator;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 기본 모델이 있으면 실패 로그의 초안을 그 모델에 맡긴다.
 * 파일이 없거나 학습기가 응답하지 않으면 규칙 초안을 남기고 다시 큐에 넣지 않는다.
 */
@Service
public class ModelDraftService {
    static final String MODEL_NOTE =
            "모델 초안은 argmax입니다. softmax 출력은 보정된 정답 확률이 아닙니다. 학습 평가 점수와 별개입니다.";
    private static final String LEASE_LOST =
            "기본 모델의 초안을 받지 못했습니다. 규칙 초안으로 남겼습니다. 자동으로 다시 추론하지 않습니다.";
    private static final String FILE_MISSING =
            "기본 모델 파일이 없습니다. 규칙 초안으로 남겼습니다. 모델 예측이 아닙니다.";

    private final ErrorCaseRepository cases;
    private final ModelVersionRepository models;
    private final IdAllocator ids;
    private final JdbcTemplate jdbcTemplate;
    private final Path modelDir;
    private final int leaseSeconds;

    public ModelDraftService(
            ErrorCaseRepository cases,
            ModelVersionRepository models,
            IdAllocator ids,
            JdbcTemplate jdbcTemplate,
            @Value("${maidops.model-dir}") String modelDir,
            @Value("${maidops.inference-lease-seconds:600}") int leaseSeconds) {
        this.cases = cases;
        this.models = models;
        this.ids = ids;
        this.jdbcTemplate = jdbcTemplate;
        this.modelDir = Path.of(modelDir).toAbsolutePath().normalize();
        this.leaseSeconds = leaseSeconds;
    }

    @PostConstruct
    void ensureModelDirectory() {
        try {
            Files.createDirectories(modelDir);
        } catch (IOException exception) {
            throw new IllegalStateException("모델 디렉터리를 만들지 못했습니다: " + modelDir, exception);
        }
    }

    @Transactional
    public void recordFailure(String jobId, String projectId, String rawText, Instant now) {
        Optional<ModelVersionEntity> selected = models.findByDefaultModelTrue();
        if (selected.isEmpty()) {
            saveRule(jobId, projectId, rawText, now, null, null);
            return;
        }
        ModelVersionEntity model = selected.get();
        if (!fileMatches(model)) {
            saveRule(jobId, projectId, rawText, now, null, FILE_MISSING);
            return;
        }
        ErrorCaseEntity errorCase = baseCase(jobId, projectId, rawText, now);
        errorCase.setDraftSource(LabelSource.MODEL);
        errorCase.setInferenceState(InferenceState.PENDING);
        errorCase.setModelVersionId(model.getId());
        cases.saveAndFlush(errorCase);
        jdbcTemplate.update(
                """
                insert into draft_inferences (
                    id, error_case_id, model_version_id, status, lease_expires_at, created_at
                ) values (?, ?, ?, 'QUEUED', ?, ?)
                """,
                ids.nextDraftInferenceId(),
                errorCase.getId(),
                model.getId(),
                Timestamp.from(now.plusSeconds(leaseSeconds)),
                Timestamp.from(now));
    }

    @Transactional
    public Optional<ClaimedInference> claim(String trainerId) {
        requireTrainerId(trainerId);
        Instant now = Instant.now();
        ClaimedInference claimed = jdbcTemplate.query(
                """
                update draft_inferences
                set status = 'RUNNING',
                    claimed_by = ?,
                    lease_expires_at = ?
                where id = (
                    select id from draft_inferences
                    where status = 'QUEUED'
                    order by created_at asc, id asc
                    for update skip locked
                    limit 1
                )
                returning id, error_case_id, model_version_id
                """,
                ps -> {
                    ps.setString(1, trainerId);
                    ps.setTimestamp(2, Timestamp.from(now.plusSeconds(leaseSeconds)));
                },
                rs -> {
                    if (!rs.next()) {
                        return null;
                    }
                    return new ClaimedInference(rs.getString(1), rs.getString(2), rs.getString(3), null, null, null);
                });
        if (claimed == null) {
            return Optional.empty();
        }
        ModelVersionEntity model = models.findById(claimed.modelVersionId())
                .orElseThrow(() -> new ApiException(409, "STATE", "초안에 연결된 모델이 없습니다.", claimed.modelVersionId()));
        ErrorCaseEntity errorCase = requireCase(claimed.errorCaseId());
        return Optional.of(new ClaimedInference(
                claimed.inferenceId(),
                claimed.errorCaseId(),
                model.getId(),
                model.getModelFile(),
                model.getChecksumSha256(),
                errorCase.getRawText()));
    }

    @Transactional
    public void complete(String trainerId, String inferenceId, ErrorLabel label) {
        requireTrainerId(trainerId);
        if (label == null) {
            throw new ApiException(400, "VALIDATION", "모델 초안 라벨이 없습니다.", "OTHER");
        }
        int updated = jdbcTemplate.update(
                """
                update draft_inferences
                set status = 'DONE', finished_at = ?
                where id = ?
                    and status = 'RUNNING'
                    and claimed_by = ?
                    and lease_expires_at >= ?
                """,
                Timestamp.from(Instant.now()),
                inferenceId,
                trainerId,
                Timestamp.from(Instant.now()));
        if (updated != 1) {
            throw new ApiException(409, "STATE", "이 모델 초안을 기록할 수 있는 상태가 아닙니다.", inferenceId);
        }
        String caseId = jdbcTemplate.queryForObject(
                "select error_case_id from draft_inferences where id = ?",
                String.class,
                inferenceId);
        String modelId = jdbcTemplate.queryForObject(
                "select model_version_id from draft_inferences where id = ?",
                String.class,
                inferenceId);
        ErrorCaseEntity errorCase = requireCase(caseId);
        if (errorCase.getInferenceState() != InferenceState.PENDING) {
            throw new ApiException(409, "STATE", "이미 닫힌 초안입니다. 라벨을 덮어쓰지 않습니다.", caseId);
        }
        Instant now = Instant.now();
        errorCase.setDraftLabel(label);
        errorCase.setCurrentLabel(label);
        errorCase.setDraftSource(LabelSource.MODEL);
        errorCase.setInferenceState(InferenceState.READY);
        errorCase.setModelVersionId(modelId);
        errorCase.setRuleVersion(null);
        errorCase.setMatchedKeyword(null);
        errorCase.addRevision(LabelRevisionEntity.create(
                label,
                ReviewStatus.DRAFT,
                LabelSource.MODEL,
                "모델 " + modelId + "의 초안입니다. " + MODEL_NOTE,
                now));
    }

    @Transactional
    public void fail(String trainerId, String inferenceId, String message) {
        requireTrainerId(trainerId);
        int updated = jdbcTemplate.update(
                """
                update draft_inferences
                set status = 'FAILED', finished_at = ?
                where id = ?
                    and status = 'RUNNING'
                    and claimed_by = ?
                """,
                Timestamp.from(Instant.now()),
                inferenceId,
                trainerId);
        if (updated != 1) {
            throw new ApiException(409, "STATE", "이 모델 초안을 실패로 닫을 수 없습니다.", inferenceId);
        }
        String caseId = jdbcTemplate.queryForObject(
                "select error_case_id from draft_inferences where id = ?",
                String.class,
                inferenceId);
        String text = message == null || message.isBlank()
                ? "모델 초안을 만들지 못했습니다."
                : message.trim();
        applyRuleFallback(requireCase(caseId), text + " 규칙 초안으로 남겼습니다. 자동으로 다시 추론하지 않습니다.");
    }

    @Transactional
    public int expireLeases() {
        Instant now = Instant.now();
        var expired = jdbcTemplate.query(
                """
                update draft_inferences
                set status = 'FAILED', finished_at = ?
                where status in ('QUEUED', 'RUNNING')
                    and lease_expires_at < ?
                returning error_case_id
                """,
                ps -> {
                    ps.setTimestamp(1, Timestamp.from(now));
                    ps.setTimestamp(2, Timestamp.from(now));
                },
                (rs, rowNum) -> rs.getString(1));
        int closed = 0;
        for (String caseId : expired) {
            ErrorCaseEntity errorCase = cases.findById(caseId).orElse(null);
            if (errorCase != null && errorCase.getInferenceState() == InferenceState.PENDING) {
                applyRuleFallback(errorCase, LEASE_LOST);
                closed++;
            }
        }
        return closed;
    }

    private void applyRuleFallback(ErrorCaseEntity errorCase, String extra) {
        if (errorCase.getInferenceState() != InferenceState.PENDING) {
            return;
        }
        RuleDraft draft = FailureRuleClassifier.classify(errorCase.getRawText());
        Instant now = Instant.now();
        errorCase.setDraftLabel(draft.label());
        errorCase.setCurrentLabel(draft.label());
        errorCase.setDraftSource(LabelSource.RULE_BASED);
        errorCase.setInferenceState(InferenceState.READY);
        errorCase.setRuleVersion(draft.ruleVersion());
        errorCase.setMatchedKeyword(draft.matchedKeyword());
        errorCase.addRevision(LabelRevisionEntity.create(
                draft.label(),
                ReviewStatus.DRAFT,
                LabelSource.RULE_BASED,
                ruleNote(draft, extra),
                now));
    }

    private void saveRule(String jobId, String projectId, String rawText, Instant now, String modelId, String extra) {
        RuleDraft draft = FailureRuleClassifier.classify(rawText);
        ErrorCaseEntity errorCase = baseCase(jobId, projectId, rawText, now);
        errorCase.setDraftLabel(draft.label());
        errorCase.setCurrentLabel(draft.label());
        errorCase.setDraftSource(LabelSource.RULE_BASED);
        errorCase.setInferenceState(InferenceState.READY);
        errorCase.setModelVersionId(modelId);
        errorCase.setRuleVersion(draft.ruleVersion());
        errorCase.setMatchedKeyword(draft.matchedKeyword());
        errorCase.addRevision(LabelRevisionEntity.create(
                draft.label(),
                ReviewStatus.DRAFT,
                LabelSource.RULE_BASED,
                ruleNote(draft, extra),
                now));
        cases.save(errorCase);
    }

    private ErrorCaseEntity baseCase(String jobId, String projectId, String rawText, Instant now) {
        ErrorCaseEntity errorCase = new ErrorCaseEntity();
        errorCase.setId(ids.nextErrorCaseId());
        errorCase.setJobId(jobId);
        errorCase.setProjectId(projectId);
        errorCase.setRawText(rawText);
        errorCase.setReviewStatus(ReviewStatus.DRAFT);
        errorCase.setOrigin(DataOrigin.SESSION);
        errorCase.setCreatedAt(now);
        return errorCase;
    }

    private boolean fileMatches(ModelVersionEntity model) {
        String modelId = model.getId();
        if (modelId == null || !modelId.matches("mv-\\d{8}")) {
            return false;
        }
        Path resolved = modelDir.resolve(modelId + ".pt").normalize();
        if (!resolved.startsWith(modelDir) || !Files.isRegularFile(resolved)) {
            return false;
        }
        try {
            byte[] bytes = Files.readAllBytes(resolved);
            String checksum = HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
            return checksum.equals(model.getChecksumSha256()) && bytes.length == model.getByteSize();
        } catch (IOException | NoSuchAlgorithmException exception) {
            return false;
        }
    }

    private ErrorCaseEntity requireCase(String caseId) {
        return cases.findById(caseId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "오류 사례를 찾지 못했습니다: " + caseId, "/review"));
    }

    private static String ruleNote(RuleDraft draft, String extra) {
        String keyword = draft.matchedKeyword() == null ? "없음" : draft.matchedKeyword();
        String note = "규칙 기반 초안입니다. 규칙 버전 " + draft.ruleVersion()
                + ". 일치 키워드: " + keyword
                + ". 이 값은 정답 확률이 아닙니다.";
        if (extra == null || extra.isBlank()) {
            return note;
        }
        return note + " " + extra;
    }

    private static void requireTrainerId(String trainerId) {
        if (trainerId == null || !trainerId.matches("^[A-Za-z0-9._:-]{4,64}$")) {
            throw new ApiException(400, "VALIDATION", "X-Trainer-Id 형식이 올바르지 않습니다.", "trainer-1");
        }
    }

    public record CompleteInferenceRequest(@NotNull ErrorLabel label) {
    }

    public record ClaimedInference(
            String inferenceId,
            String errorCaseId,
            String modelVersionId,
            String modelFile,
            String checksumSha256,
            String rawText) {
    }
}
