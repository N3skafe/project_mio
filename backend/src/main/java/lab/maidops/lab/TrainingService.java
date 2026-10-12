package lab.maidops.lab;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import jakarta.persistence.EntityManager;
import lab.maidops.api.ApiException;
import lab.maidops.api.CursorCodec;
import lab.maidops.api.PageResponse;
import lab.maidops.domain.DatasetSplit;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.ReviewStatus;
import lab.maidops.domain.TrainingStatus;
import lab.maidops.errorcase.ErrorCaseEntity;
import lab.maidops.errorcase.ErrorCaseRepository;
import lab.maidops.job.IdAllocator;
import lab.maidops.lab.ClassificationMetrics.ClassScore;
import lab.maidops.lab.ClassificationMetrics.Report;
import lab.maidops.lab.DatasetSplitter.AssignedRow;
import lab.maidops.lab.DatasetSplitter.Row;
import lab.maidops.lab.LabPayloads.ClaimedTraining;
import lab.maidops.lab.LabPayloads.ClassCount;
import lab.maidops.lab.LabPayloads.ClassMetricRequest;
import lab.maidops.lab.LabPayloads.ClassScoreResponse;
import lab.maidops.lab.LabPayloads.CompleteTrainingRequest;
import lab.maidops.lab.LabPayloads.ExampleList;
import lab.maidops.lab.LabPayloads.HeartbeatResponse;
import lab.maidops.lab.LabPayloads.LabStatusResponse;
import lab.maidops.lab.LabPayloads.ModelVersionResponse;
import lab.maidops.lab.LabPayloads.RunBrief;
import lab.maidops.lab.LabPayloads.SplitPreview;
import lab.maidops.lab.LabPayloads.TrainerExample;
import lab.maidops.lab.LabPayloads.TrainingRunResponse;
import lab.maidops.lab.TrainingPolicy.Gate;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TrainingService {
    private static final String LEASE_LOST = "학습 프로세스가 응답하지 않습니다. 자동으로 다시 학습하지 않습니다.";
    private static final String EMBEDDING_NOTE =
            "문장 임베딩은 로컬 고정 해시 hashing-char-ngram-v1 입니다. 외부 모델 파일을 받지 않습니다.";

    private final ErrorCaseRepository cases;
    private final TrainingRunRepository runs;
    private final ModelVersionRepository models;
    private final TrainingExampleRepository examples;
    private final SplitAnchorRepository anchors;
    private final IdAllocator ids;
    private final JdbcTemplate jdbcTemplate;
    private final EntityManager entityManager;
    private final ObjectMapper json;
    private final Path modelDir;
    private final int leaseSeconds;

    public TrainingService(
            ErrorCaseRepository cases,
            TrainingRunRepository runs,
            ModelVersionRepository models,
            TrainingExampleRepository examples,
            SplitAnchorRepository anchors,
            IdAllocator ids,
            JdbcTemplate jdbcTemplate,
            EntityManager entityManager,
            ObjectMapper json,
            @Value("${maidops.model-dir}") String modelDir,
            @Value("${maidops.training-lease-seconds:120}") int leaseSeconds) {
        this.cases = cases;
        this.runs = runs;
        this.models = models;
        this.examples = examples;
        this.anchors = anchors;
        this.ids = ids;
        this.jdbcTemplate = jdbcTemplate;
        this.entityManager = entityManager;
        this.json = json;
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

    @Transactional(readOnly = true)
    public LabStatusResponse status() {
        Prepared prepared = prepare();
        Gate gate = prepared.gate();
        return new LabStatusResponse(
                gate.eligible(),
                gate.reasons(),
                prepared.rows().size(),
                (int) cases.countByReviewStatus(ReviewStatus.DRAFT),
                (int) cases.countByReviewStatus(ReviewStatus.DEFERRED),
                classCounts(gate),
                thresholds(),
                preview(gate),
                activeBrief(),
                models.findByDefaultModelTrue().map(this::toModel).orElse(null),
                models.findFirstByOrderByCreatedAtDescIdDesc().map(this::toModel).orElse(null),
                models.findAll().stream()
                        .sorted(java.util.Comparator.comparing(ModelVersionEntity::getCreatedAt)
                                .thenComparing(ModelVersionEntity::getId))
                        .map(this::toModel)
                        .toList(),
                TrainingPolicy.EMBEDDING_ID,
                TrainingPolicy.LABEL_SCHEMA,
                false,
                EMBEDDING_NOTE);
    }

    @Transactional
    public TrainingRunResponse createRun() {
        if (runs.existsByStatusIn(List.of(TrainingStatus.QUEUED, TrainingStatus.RUNNING))) {
            throw new ApiException(409, "STATE", "이미 진행 중인 학습이 있습니다.", "끝난 뒤 다시 시작하세요.");
        }
        Prepared prepared = prepare();
        Gate gate = prepared.gate();
        if (!gate.eligible()) {
            throw new ApiException(
                    409,
                    "STATE",
                    String.join(" ", gate.reasons()),
                    "확정 라벨을 더 모은 뒤 다시 요청하세요.");
        }
        assertGroupsStayTogether(prepared.rows());
        Instant now = Instant.now();
        persistAnchors(prepared.rows(), now);
        TrainingRunEntity run = new TrainingRunEntity();
        run.setId(ids.nextTrainingRunId());
        run.setCreatedAt(now);
        run.setStatus(TrainingStatus.QUEUED);
        run.setDatasetFingerprint(DatasetSplitter.fingerprint(prepared.rows()));
        run.setLabelSchemaVersion(TrainingPolicy.LABEL_SCHEMA);
        run.setEmbeddingId(TrainingPolicy.EMBEDDING_ID);
        run.setSplitPolicy(TrainingPolicy.SPLIT_POLICY);
        try {
            runs.saveAndFlush(run);
        } catch (DataIntegrityViolationException exception) {
            throw new ApiException(409, "STATE", "이미 진행 중인 학습이 있습니다.", "끝난 뒤 다시 시작하세요.");
        }
        for (AssignedRow row : prepared.rows()) {
            TrainingExampleEntity example = new TrainingExampleEntity();
            example.setTrainingRunId(run.getId());
            example.setErrorCaseId(row.id());
            example.setGroupKey(row.groupKey());
            example.setSplit(row.split());
            example.setLabel(row.label());
            example.setTemplateHash(row.templateHash());
            example.setTextSha256(DatasetSplitter.sha256(row.rawText()));
            examples.save(example);
        }
        return toRun(run);
    }

    @Transactional(readOnly = true)
    public PageResponse<TrainingRunResponse> listRuns(String cursor, Integer limit) {
        int pageSize = pageSize(limit);
        CursorCodec.Cursor position = CursorCodec.decode(cursor);
        List<TrainingRunEntity> rows = position == null
                ? runs.firstPage(pageSize + 1)
                : runs.pageAfter(position.createdAt(), position.id(), pageSize + 1);
        return page(rows, pageSize, this::toRun);
    }

    @Transactional(readOnly = true)
    public TrainingRunResponse getRun(String runId) {
        return toRun(requireRun(runId));
    }

    @Transactional
    public TrainingRunResponse cancel(String runId) {
        TrainingRunEntity run = requireRun(runId);
        if (run.getStatus() == TrainingStatus.QUEUED) {
            run.setStatus(TrainingStatus.FAILED);
            run.setFinishedAt(Instant.now());
            run.setErrorMessage("사용자가 대기 중인 학습을 취소했습니다. 자동으로 다시 시작하지 않습니다.");
            return toRun(run);
        }
        if (run.getStatus() == TrainingStatus.RUNNING) {
            if (run.getCancelRequestedAt() == null) {
                run.setCancelRequestedAt(Instant.now());
            }
            return toRun(run);
        }
        throw new ApiException(409, "STATE", "끝난 학습은 취소할 수 없습니다.", runId);
    }

    @Transactional(readOnly = true)
    public PageResponse<ModelVersionResponse> listModels(String cursor, Integer limit) {
        int pageSize = pageSize(limit);
        CursorCodec.Cursor position = CursorCodec.decode(cursor);
        List<ModelVersionEntity> rows = position == null
                ? models.firstPage(pageSize + 1)
                : models.pageAfter(position.createdAt(), position.id(), pageSize + 1);
        return page(rows, pageSize, this::toModel);
    }

    @Transactional
    public ModelVersionResponse selectDefault(String modelId) {
        if (!models.existsById(modelId)) {
            throw new ApiException(404, "NOT_FOUND", "모델 버전을 찾지 못했습니다: " + modelId, "/lab");
        }
        jdbcTemplate.update("update model_versions set is_default = false");
        jdbcTemplate.update("update model_versions set is_default = true where id = ?", modelId);
        entityManager.flush();
        entityManager.clear();
        return toModel(models.findById(modelId).orElseThrow());
    }

    @Transactional
    public Optional<ClaimedTraining> claim(String trainerId) {
        requireTrainerId(trainerId);
        Instant now = Instant.now();
        ClaimedRow claimed = jdbcTemplate.query(
                """
                update training_runs
                set status = 'RUNNING',
                    claimed_by = ?,
                    started_at = coalesce(started_at, ?),
                    lease_expires_at = ?,
                    reserved_model_id = coalesce(
                        reserved_model_id,
                        'mv-' || lpad(nextval('model_version_id_seq')::text, 8, '0')
                    )
                where id = (
                    select id
                    from training_runs
                    where status = 'QUEUED'
                    order by created_at, id
                    for update skip locked
                    limit 1
                )
                returning id, reserved_model_id, embedding_id, label_schema_version, dataset_fingerprint
                """,
                ps -> {
                    ps.setString(1, trainerId);
                    ps.setTimestamp(2, Timestamp.from(now));
                    ps.setTimestamp(3, Timestamp.from(now.plusSeconds(leaseSeconds)));
                },
                rs -> {
                    if (!rs.next()) {
                        return null;
                    }
                    return new ClaimedRow(
                            rs.getString(1),
                            rs.getString(2),
                            rs.getString(3),
                            rs.getString(4),
                            rs.getString(5));
                });
        if (claimed == null) {
            return Optional.empty();
        }
        entityManager.flush();
        entityManager.clear();
        return Optional.of(new ClaimedTraining(
                claimed.id(),
                claimed.modelId(),
                claimed.modelId() + ".pt",
                claimed.embeddingId(),
                claimed.labelSchema(),
                claimed.fingerprint(),
                TrainingPolicy.SEED));
    }

    @Transactional(readOnly = true)
    public ExampleList examples(String trainerId, String runId) {
        TrainingRunEntity run = requireOwnedRunning(trainerId, runId);
        Map<String, String> texts = new LinkedHashMap<>();
        for (ErrorCaseEntity errorCase : cases.findAllById(examples.findByTrainingRunIdOrderByErrorCaseIdAsc(run.getId())
                .stream()
                .map(TrainingExampleEntity::getErrorCaseId)
                .toList())) {
            texts.put(errorCase.getId(), errorCase.getRawText());
        }
        List<TrainerExample> items = new ArrayList<>();
        for (TrainingExampleEntity example : examples.findByTrainingRunIdOrderByErrorCaseIdAsc(run.getId())) {
            String text = texts.get(example.getErrorCaseId());
            if (text == null) {
                throw new ApiException(409, "STATE", "학습 사례의 원문을 찾지 못했습니다.", example.getErrorCaseId());
            }
            items.add(new TrainerExample(
                    example.getErrorCaseId(),
                    text,
                    example.getLabel(),
                    example.getSplit(),
                    example.getGroupKey()));
        }
        return new ExampleList(items);
    }

    @Transactional
    public HeartbeatResponse heartbeat(String trainerId, String runId) {
        requireTrainerId(trainerId);
        Instant lease = Instant.now().plusSeconds(leaseSeconds);
        int updated = jdbcTemplate.update(
                """
                update training_runs
                set lease_expires_at = ?
                where id = ? and claimed_by = ? and status = 'RUNNING'
                """,
                Timestamp.from(lease),
                runId,
                trainerId);
        if (updated == 0) {
            throw new ApiException(409, "STATE", "이 학습의 임대가 없습니다.", runId);
        }
        entityManager.flush();
        entityManager.clear();
        TrainingRunEntity run = requireRun(runId);
        return new HeartbeatResponse(run.getCancelRequestedAt() != null);
    }

    @Transactional
    public ModelVersionResponse complete(String trainerId, String runId, CompleteTrainingRequest request) {
        TrainingRunEntity run = requireOwnedRunning(trainerId, runId);
        if (run.getCancelRequestedAt() != null) {
            throw new ApiException(409, "STATE", "취소된 학습은 모델로 저장하지 않습니다.", runId);
        }
        if (!TrainingPolicy.EMBEDDING_ID.equals(request.embeddingId())
                || !TrainingPolicy.LABEL_SCHEMA.equals(request.labelSchemaVersion())) {
            throw new ApiException(400, "VALIDATION", "임베딩 또는 라벨 체계가 이 연구실의 고정 값과 다릅니다.", TrainingPolicy.EMBEDDING_ID);
        }
        if (request.seed() != TrainingPolicy.SEED) {
            throw new ApiException(400, "VALIDATION", "학습 seed는 " + TrainingPolicy.SEED + " 이어야 합니다.", "42");
        }
        requireConfig(request.config());
        Report modelReport = report(request.confusionMatrix(), request.macroF1(), request.perClass());
        Report baselineReport = report(
                request.baselineConfusionMatrix(),
                request.baselineMacroF1(),
                request.baselinePerClass());
        StoredFile stored = readModelFile(run.getReservedModelId());
        String metrics = writeJson(new StoredMetrics(
                modelReport.macroF1(),
                modelReport.perClass(),
                modelReport.confusion(),
                baselineReport.macroF1(),
                baselineReport.perClass(),
                baselineReport.confusion(),
                TrainingPolicy.PROBABILITY_NOTE));
        String config = writeJson(request.config());
        Instant now = Instant.now();
        int updated = jdbcTemplate.update(
                """
                update training_runs
                set status = 'SUCCEEDED',
                    finished_at = ?,
                    config_json = ?,
                    metrics_json = ?,
                    code_version = ?,
                    lease_expires_at = null
                where id = ? and claimed_by = ? and status = 'RUNNING' and cancel_requested_at is null
                """,
                Timestamp.from(now),
                config,
                metrics,
                request.codeVersion(),
                runId,
                trainerId);
        if (updated == 0) {
            throw new ApiException(409, "STATE", "취소되었거나 끝난 학습은 모델로 저장하지 않습니다.", runId);
        }
        ModelVersionEntity model = new ModelVersionEntity();
        model.setId(run.getReservedModelId());
        model.setTrainingRunId(runId);
        model.setCreatedAt(now);
        model.setEmbeddingId(request.embeddingId());
        model.setLabelSchemaVersion(request.labelSchemaVersion());
        model.setDatasetFingerprint(run.getDatasetFingerprint());
        model.setCodeVersion(request.codeVersion());
        model.setDevice(request.device());
        model.setSeed(request.seed());
        model.setConfigJson(config);
        model.setMetricsJson(metrics);
        model.setModelFile(stored.fileName());
        model.setChecksumSha256(stored.checksum());
        model.setByteSize(stored.byteSize());
        model.setDefaultModel(false);
        models.save(model);
        entityManager.flush();
        entityManager.clear();
        return toModel(models.findById(model.getId()).orElseThrow());
    }

    @Transactional
    public TrainingRunResponse fail(String trainerId, String runId, String message) {
        TrainingRunEntity run = requireOwnedRunning(trainerId, runId);
        run.setStatus(TrainingStatus.FAILED);
        run.setFinishedAt(Instant.now());
        run.setLeaseExpiresAt(null);
        run.setErrorMessage(message.trim());
        return toRun(run);
    }

    @Transactional
    public int expireLeases() {
        return jdbcTemplate.update(
                """
                update training_runs
                set status = 'FAILED',
                    finished_at = ?,
                    error_message = ?,
                    lease_expires_at = null
                where status = 'RUNNING'
                    and lease_expires_at is not null
                    and lease_expires_at < ?
                """,
                Timestamp.from(Instant.now()),
                LEASE_LOST,
                Timestamp.from(Instant.now()));
    }

    private Prepared prepare() {
        int draftCount = (int) cases.countByReviewStatus(ReviewStatus.DRAFT);
        int deferredCount = (int) cases.countByReviewStatus(ReviewStatus.DEFERRED);
        List<Row> confirmed = cases
                .findByReviewStatusInOrderByCreatedAtAscIdAsc(List.of(ReviewStatus.APPROVED, ReviewStatus.REVISED))
                .stream()
                .map(errorCase -> new Row(
                        errorCase.getId(),
                        errorCase.getJobId(),
                        errorCase.getRawText(),
                        errorCase.getCurrentLabel()))
                .toList();
        Map<String, DatasetSplit> anchorMap = new LinkedHashMap<>();
        for (SplitAnchorEntity anchor : anchors.findAll()) {
            anchorMap.put(anchor.getTemplateHash(), anchor.getSplit());
        }
        List<AssignedRow> assigned = DatasetSplitter.assign(confirmed, anchorMap);
        return new Prepared(assigned, TrainingPolicy.evaluate(assigned, draftCount, deferredCount));
    }

    private void persistAnchors(List<AssignedRow> rows, Instant now) {
        for (AssignedRow row : rows) {
            SplitAnchorEntity anchor = anchors.findById(row.templateHash()).orElse(null);
            if (anchor == null) {
                SplitAnchorEntity created = new SplitAnchorEntity();
                created.setTemplateHash(row.templateHash());
                created.setSplit(row.split());
                created.setPolicyVersion(TrainingPolicy.SPLIT_POLICY);
                created.setCreatedAt(now);
                anchors.save(created);
            } else if (row.split().holdoutRank() > anchor.getSplit().holdoutRank()) {
                anchor.setSplit(row.split());
            }
        }
    }

    private static void assertGroupsStayTogether(List<AssignedRow> rows) {
        Map<String, DatasetSplit> seen = new LinkedHashMap<>();
        for (AssignedRow row : rows) {
            DatasetSplit previous = seen.putIfAbsent(row.groupKey(), row.split());
            if (previous != null && previous != row.split()) {
                throw new ApiException(
                        409,
                        "STATE",
                        "같은 오류 그룹이 둘 이상의 분할에 있습니다. 학습을 만들지 않았습니다.",
                        row.groupKey());
            }
        }
    }

    private Report report(List<List<Integer>> matrix, Double macro, List<ClassMetricRequest> perClass) {
        try {
            Report computed = ClassificationMetrics.fromConfusion(toMatrix(matrix));
            ClassificationMetrics.assertMatches(
                    computed,
                    new ClassificationMetrics.Submitted(macro, toScores(perClass)));
            return computed;
        } catch (IllegalArgumentException exception) {
            throw new ApiException(400, "VALIDATION", exception.getMessage(), "");
        }
    }

    private static int[][] toMatrix(List<List<Integer>> rows) {
        int size = ClassificationMetrics.LABELS.size();
        if (rows.size() != size) {
            throw new IllegalArgumentException("혼동행렬은 라벨 수와 같은 정사각 행렬이어야 합니다.");
        }
        int[][] matrix = new int[size][size];
        for (int rowIndex = 0; rowIndex < size; rowIndex++) {
            List<Integer> row = rows.get(rowIndex);
            if (row == null || row.size() != size) {
                throw new IllegalArgumentException("혼동행렬은 라벨 수와 같은 정사각 행렬이어야 합니다.");
            }
            for (int column = 0; column < size; column++) {
                Integer value = row.get(column);
                if (value == null) {
                    throw new IllegalArgumentException("혼동행렬에는 빈 칸을 넣을 수 없습니다.");
                }
                matrix[rowIndex][column] = value;
            }
        }
        return matrix;
    }

    private static List<ClassScore> toScores(List<ClassMetricRequest> items) {
        return items.stream()
                .map(item -> new ClassScore(item.label(), item.precision(), item.recall(), item.f1(), item.support()))
                .toList();
    }

    private static void requireConfig(Map<String, Object> config) {
        if (number(config, "embedding_dim") != TrainingPolicy.EMBEDDING_DIM
                || number(config, "hidden_dim") != TrainingPolicy.HIDDEN_DIM) {
            throw new ApiException(
                    400,
                    "VALIDATION",
                    "학습 설정은 고정 임베딩 차원과 은닉층 크기를 그대로 기록해야 합니다.",
                    "embedding_dim=256 hidden_dim=64");
        }
        if (number(config, "epochs_ran") < 1 || number(config, "max_epochs") < 1 || number(config, "batch_size") < 1) {
            throw new ApiException(400, "VALIDATION", "학습 설정에 실제 반복 횟수가 없습니다.", "epochs_ran");
        }
        number(config, "learning_rate");
        number(config, "dropout");
    }

    private static int number(Map<String, Object> config, String key) {
        Object value = config.get(key);
        if (!(value instanceof Number number) || !Double.isFinite(number.doubleValue())) {
            throw new ApiException(400, "VALIDATION", "학습 설정에 " + key + "가 없습니다.", key);
        }
        return number.intValue();
    }

    private StoredFile readModelFile(String modelId) {
        if (modelId == null || !modelId.matches("mv-\\d{8}")) {
            throw new ApiException(409, "STATE", "예약된 모델 파일 이름이 없습니다.", "");
        }
        String fileName = modelId + ".pt";
        Path resolved = modelDir.resolve(fileName).normalize();
        if (!resolved.startsWith(modelDir)) {
            throw new ApiException(400, "VALIDATION", "모델 경로는 모델 디렉터리 안이어야 합니다.", fileName);
        }
        if (!Files.isRegularFile(resolved)) {
            throw new ApiException(409, "STATE", "모델 파일이 없습니다. 평가를 저장하지 않았습니다.", fileName);
        }
        try {
            byte[] bytes = Files.readAllBytes(resolved);
            return new StoredFile(fileName, sha256(bytes), bytes.length);
        } catch (IOException exception) {
            throw new ApiException(409, "STATE", "모델 파일을 읽지 못했습니다. 평가를 저장하지 않았습니다.", fileName);
        }
    }

    private TrainingRunEntity requireOwnedRunning(String trainerId, String runId) {
        requireTrainerId(trainerId);
        TrainingRunEntity run = requireRun(runId);
        if (run.getStatus() != TrainingStatus.RUNNING || !trainerId.equals(run.getClaimedBy())) {
            throw new ApiException(409, "STATE", "이 학습을 기록할 수 있는 상태가 아닙니다.", runId);
        }
        return run;
    }

    private TrainingRunEntity requireRun(String runId) {
        return runs.findById(runId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "학습 실행을 찾지 못했습니다: " + runId, "/lab"));
    }

    private static void requireTrainerId(String trainerId) {
        if (trainerId == null || !trainerId.matches("^[A-Za-z0-9._:-]{4,64}$")) {
            throw new ApiException(400, "VALIDATION", "X-Trainer-Id 형식이 올바르지 않습니다.", "trainer-1");
        }
    }

    private RunBrief activeBrief() {
        return runs.findAll().stream()
                .filter(run -> run.getStatus() == TrainingStatus.QUEUED || run.getStatus() == TrainingStatus.RUNNING)
                .findFirst()
                .map(run -> new RunBrief(run.getId(), run.getStatus()))
                .orElse(null);
    }

    private TrainingRunResponse toRun(TrainingRunEntity run) {
        ModelVersionResponse model = models.findAll().stream()
                .filter(item -> run.getId().equals(item.getTrainingRunId()))
                .findFirst()
                .map(this::toModel)
                .orElse(null);
        return new TrainingRunResponse(
                run.getId(),
                run.getStatus(),
                run.getCreatedAt(),
                run.getStartedAt(),
                run.getFinishedAt(),
                run.getDatasetFingerprint(),
                run.getLabelSchemaVersion(),
                run.getEmbeddingId(),
                run.getSplitPolicy(),
                run.getCodeVersion(),
                run.getErrorMessage(),
                run.getReservedModelId(),
                run.getCancelRequestedAt(),
                splitOf(run.getId()),
                model);
    }

    private SplitPreview splitOf(String runId) {
        int train = 0;
        int val = 0;
        int test = 0;
        java.util.Set<ErrorLabel> trainLabels = java.util.EnumSet.noneOf(ErrorLabel.class);
        java.util.Set<ErrorLabel> valLabels = java.util.EnumSet.noneOf(ErrorLabel.class);
        java.util.Set<ErrorLabel> testLabels = java.util.EnumSet.noneOf(ErrorLabel.class);
        for (TrainingExampleEntity example : examples.findByTrainingRunIdOrderByErrorCaseIdAsc(runId)) {
            if (example.getSplit() == DatasetSplit.TRAIN) {
                train++;
                trainLabels.add(example.getLabel());
            } else if (example.getSplit() == DatasetSplit.VAL) {
                val++;
                valLabels.add(example.getLabel());
            } else if (example.getSplit() == DatasetSplit.TEST) {
                test++;
                testLabels.add(example.getLabel());
            }
        }
        return new SplitPreview(train, val, test, trainLabels.size(), valLabels.size(), testLabels.size());
    }

    private ModelVersionResponse toModel(ModelVersionEntity model) {
        StoredMetrics metrics = readJson(model.getMetricsJson(), StoredMetrics.class);
        return new ModelVersionResponse(
                model.getId(),
                model.getTrainingRunId(),
                model.getCreatedAt(),
                model.getEmbeddingId(),
                model.getLabelSchemaVersion(),
                model.getDatasetFingerprint(),
                model.getCodeVersion(),
                model.getDevice(),
                model.getSeed(),
                metrics.macroF1(),
                metrics.baselineMacroF1(),
                metrics.perClass().stream().map(TrainingService::score).toList(),
                matrix(metrics.confusion()),
                metrics.baselinePerClass().stream().map(TrainingService::score).toList(),
                matrix(metrics.baselineConfusion()),
                metrics.probabilityNote(),
                model.isDefaultModel());
    }

    private static ClassScoreResponse score(ClassScore score) {
        return new ClassScoreResponse(score.label(), score.precision(), score.recall(), score.f1(), score.support());
    }

    private static List<List<Integer>> matrix(int[][] confusion) {
        List<List<Integer>> rows = new ArrayList<>();
        for (int[] row : confusion) {
            List<Integer> values = new ArrayList<>();
            for (int value : row) {
                values.add(value);
            }
            rows.add(values);
        }
        return rows;
    }

    private static List<ClassCount> classCounts(Gate gate) {
        List<ClassCount> counts = new ArrayList<>();
        for (ErrorLabel label : ErrorLabel.values()) {
            counts.add(new ClassCount(label, gate.classCounts().getOrDefault(label, 0)));
        }
        return counts;
    }

    private static SplitPreview preview(Gate gate) {
        return new SplitPreview(
                gate.trainCount(),
                gate.valCount(),
                gate.testCount(),
                gate.trainLabels(),
                gate.valLabels(),
                gate.testLabels());
    }

    private static LabPayloads.Thresholds thresholds() {
        return new LabPayloads.Thresholds(
                TrainingPolicy.MIN_CONFIRMED,
                TrainingPolicy.MIN_DISTINCT_LABELS,
                TrainingPolicy.MIN_TRAIN,
                TrainingPolicy.MIN_VAL,
                TrainingPolicy.MIN_TEST,
                TrainingPolicy.MIN_LABELS_IN_TRAIN,
                TrainingPolicy.MIN_LABELS_IN_VAL,
                TrainingPolicy.MIN_LABELS_IN_TEST);
    }

    private String writeJson(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new ApiException(400, "VALIDATION", "학습 결과를 JSON으로 저장하지 못했습니다.", "");
        }
    }

    private <T> T readJson(String value, Class<T> type) {
        try {
            return json.readValue(value, type);
        } catch (JsonProcessingException exception) {
            throw new ApiException(500, "INTERNAL", "저장된 평가를 읽지 못했습니다.", "");
        }
    }

    private static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }

    private static int pageSize(Integer limit) {
        int resolved = limit == null ? 50 : limit;
        if (resolved < 1 || resolved > 100) {
            throw new ApiException(400, "VALIDATION", "limit은 1 이상 100 이하여야 합니다.", "50");
        }
        return resolved;
    }

    private static <T, R> PageResponse<R> page(List<T> rows, int pageSize, java.util.function.Function<T, R> mapper) {
        boolean more = rows.size() > pageSize;
        List<T> page = more ? rows.subList(0, pageSize) : rows;
        String next = null;
        if (more && !page.isEmpty()) {
            T last = page.get(page.size() - 1);
            if (last instanceof TrainingRunEntity run) {
                next = CursorCodec.encode(run.getCreatedAt(), run.getId());
            } else if (last instanceof ModelVersionEntity model) {
                next = CursorCodec.encode(model.getCreatedAt(), model.getId());
            }
        }
        return new PageResponse<>(page.stream().map(mapper).toList(), next);
    }

    private record Prepared(List<AssignedRow> rows, Gate gate) {
    }

    private record ClaimedRow(String id, String modelId, String embeddingId, String labelSchema, String fingerprint) {
    }

    private record StoredFile(String fileName, String checksum, long byteSize) {
    }

    public record StoredMetrics(
            double macroF1,
            List<ClassScore> perClass,
            int[][] confusion,
            double baselineMacroF1,
            List<ClassScore> baselinePerClass,
            int[][] baselineConfusion,
            String probabilityNote) {
    }
}
