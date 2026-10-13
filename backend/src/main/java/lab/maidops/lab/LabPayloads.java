package lab.maidops.lab;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lab.maidops.domain.DatasetSplit;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.TrainingStatus;

public final class LabPayloads {
    private LabPayloads() {
    }

    public record ClassCount(ErrorLabel label, int count) {
    }

    public record Thresholds(
            int minConfirmed,
            int minDistinctLabels,
            int minTrain,
            int minVal,
            int minTest,
            int minLabelsInTrain,
            int minLabelsInVal,
            int minLabelsInTest) {
    }

    public record SplitPreview(
            int train,
            int val,
            int test,
            int trainLabels,
            int valLabels,
            int testLabels) {
    }

    public record RunBrief(String id, TrainingStatus status) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ClassScoreResponse(
            ErrorLabel label,
            Double precision,
            Double recall,
            Double f1,
            int support,
            int predictedCount,
            int falsePositives,
            boolean includedInMacro) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record ModelVersionResponse(
            String id,
            String trainingRunId,
            Instant createdAt,
            String embeddingId,
            String labelSchemaVersion,
            String datasetFingerprint,
            String codeVersion,
            String device,
            int seed,
            double macroF1,
            double baselineMacroF1,
            List<ClassScoreResponse> perClass,
            List<List<Integer>> confusionMatrix,
            List<ClassScoreResponse> baselinePerClass,
            List<List<Integer>> baselineConfusionMatrix,
            String probabilityNote,
            @JsonProperty("is_default") boolean defaultModel,
            String metricPolicy,
            List<String> includedLabels,
            Integer evaluationSampleCount,
            String evaluationFingerprint,
            boolean checkpointEvaluated) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record TrainingRunResponse(
            String id,
            TrainingStatus status,
            Instant createdAt,
            Instant startedAt,
            Instant finishedAt,
            String datasetFingerprint,
            String labelSchemaVersion,
            String embeddingId,
            String splitPolicy,
            String codeVersion,
            String errorMessage,
            String reservedModelId,
            Instant cancelRequestedAt,
            SplitPreview split,
            ModelVersionResponse model) {
    }

    @JsonInclude(JsonInclude.Include.NON_NULL)
    public record LabStatusResponse(
            boolean eligible,
            List<String> reasons,
            int confirmedCount,
            int draftCount,
            int deferredCount,
            List<ClassCount> classCounts,
            Thresholds thresholds,
            SplitPreview splitPreview,
            RunBrief activeRun,
            ModelVersionResponse defaultModel,
            ModelVersionResponse latestModel,
            List<ModelVersionResponse> models,
            String embeddingId,
            String labelSchemaVersion,
            boolean downloadRequired,
            String embeddingNote) {
    }

    public record ClaimedTraining(
            String trainingRunId,
            String reservedModelId,
            String modelFile,
            String embeddingId,
            String labelSchemaVersion,
            String datasetFingerprint,
            int seed) {
    }

    public record TrainerExample(
            String errorCaseId,
            String rawText,
            ErrorLabel label,
            DatasetSplit split,
            String groupKey) {
    }

    public record ExampleList(List<TrainerExample> items) {
    }

    public record HeartbeatResponse(boolean cancelRequested) {
    }

    public record ClassMetricRequest(
            @NotNull ErrorLabel label,
            Double precision,
            Double recall,
            Double f1,
            @NotNull Integer support,
            @NotNull Integer predictedCount,
            @NotNull Integer falsePositives,
            @NotNull Boolean includedInMacro) {
    }

    public record CompleteTrainingRequest(
            @NotBlank String embeddingId,
            @NotBlank String labelSchemaVersion,
            @NotBlank @Pattern(regexp = "unknown|[0-9a-f]{7,40}") String codeVersion,
            @NotBlank @Pattern(regexp = "cpu|cuda") String device,
            @NotNull Integer seed,
            @NotNull Map<String, Object> config,
            @NotNull Double macroF1,
            @Valid @NotNull @Size(min = 5, max = 5) List<ClassMetricRequest> perClass,
            @NotNull List<List<Integer>> confusionMatrix,
            @NotNull Double baselineMacroF1,
            @Valid @NotNull @Size(min = 5, max = 5) List<ClassMetricRequest> baselinePerClass,
            @NotNull List<List<Integer>> baselineConfusionMatrix,
            @NotBlank String metricPolicy,
            @NotNull @Size(min = 5, max = 5) List<String> labelOrder,
            @NotNull List<String> includedLabels,
            @NotNull Integer evaluationSampleCount,
            @NotBlank String evaluationFingerprint,
            @NotNull Boolean checkpointEvaluated) {
    }

    public record FailTrainingRequest(@NotBlank @Size(max = 2000) String message) {
    }
}
