package lab.maidops.lab;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;

import lab.maidops.domain.DatasetSplit;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.lab.DatasetSplitter.AssignedRow;

public final class TrainingPolicy {
    public static final int MIN_CONFIRMED = 20;
    public static final int MIN_DISTINCT_LABELS = 2;
    public static final int MIN_TRAIN = 8;
    public static final int MIN_VAL = 4;
    public static final int MIN_TEST = 4;
    public static final int MIN_LABELS_IN_TRAIN = 2;
    public static final int MIN_LABELS_IN_VAL = 2;
    public static final int MIN_LABELS_IN_TEST = 2;
    public static final int SEED = 42;
    public static final int EMBEDDING_DIM = 256;
    public static final int HIDDEN_DIM = 64;
    public static final String LABEL_SCHEMA = "labels-1";
    public static final String EMBEDDING_ID = "hashing-char-ngram-v1";
    public static final String SPLIT_POLICY = "split-1";
    public static final String PROBABILITY_NOTE = "softmax 출력은 보정된 정답 확률이 아닙니다. 점수는 테스트 분할에서 센 값입니다.";
    /** 학습기가 쓰는 상한과 같다. 이 값을 넘는 파일은 읽지 않는다. */
    public static final int MAX_MODEL_BYTES = 8 * 1024 * 1024;

    private TrainingPolicy() {
    }

    public record Gate(
            boolean eligible,
            List<String> reasons,
            Map<ErrorLabel, Integer> classCounts,
            int trainCount,
            int valCount,
            int testCount,
            int trainLabels,
            int valLabels,
            int testLabels) {
    }

    public static Gate evaluate(List<AssignedRow> rows, int draftCount, int deferredCount) {
        Map<ErrorLabel, Integer> counts = new EnumMap<>(ErrorLabel.class);
        for (ErrorLabel label : ErrorLabel.values()) {
            counts.put(label, 0);
        }
        for (AssignedRow row : rows) {
            counts.merge(row.label(), 1, Integer::sum);
        }
        int distinct = (int) counts.values().stream().filter(count -> count > 0).count();
        int train = count(rows, DatasetSplit.TRAIN);
        int val = count(rows, DatasetSplit.VAL);
        int test = count(rows, DatasetSplit.TEST);
        int trainLabels = labels(rows, DatasetSplit.TRAIN);
        int valLabels = labels(rows, DatasetSplit.VAL);
        int testLabels = labels(rows, DatasetSplit.TEST);
        List<String> reasons = new ArrayList<>();
        if (rows.size() < MIN_CONFIRMED) {
            reasons.add("확정 사례가 " + rows.size() + "건입니다. 학습에는 " + MIN_CONFIRMED + "건 이상이 필요합니다.");
        }
        if (distinct < MIN_DISTINCT_LABELS) {
            reasons.add("확정 라벨이 " + distinct + "종입니다. 학습에는 " + MIN_DISTINCT_LABELS + "종 이상이 필요합니다.");
        }
        if (train < MIN_TRAIN) {
            reasons.add("학습 분할이 " + train + "건입니다. " + MIN_TRAIN + "건 이상이 필요합니다.");
        }
        if (val < MIN_VAL) {
            reasons.add("검증 분할이 " + val + "건입니다. " + MIN_VAL + "건 이상이 필요합니다.");
        }
        if (test < MIN_TEST) {
            reasons.add("테스트 분할이 " + test + "건입니다. " + MIN_TEST + "건 이상이 필요합니다.");
        }
        if (trainLabels < MIN_LABELS_IN_TRAIN) {
            reasons.add("학습 분할의 라벨이 " + trainLabels + "종입니다. " + MIN_LABELS_IN_TRAIN + "종 이상이 필요합니다.");
        }
        if (valLabels < MIN_LABELS_IN_VAL) {
            reasons.add("검증 분할의 라벨이 " + valLabels + "종입니다. " + MIN_LABELS_IN_VAL + "종 이상이 필요합니다.");
        }
        if (testLabels < MIN_LABELS_IN_TEST) {
            reasons.add("테스트 분할의 라벨이 " + testLabels + "종입니다. " + MIN_LABELS_IN_TEST + "종 이상이 필요합니다.");
        }
        if (!reasons.isEmpty() && (draftCount > 0 || deferredCount > 0)) {
            reasons.add("초안 " + draftCount + "건과 보류 " + deferredCount + "건은 확정 라벨이 아니므로 학습 수에 넣지 않았습니다.");
        }
        return new Gate(reasons.isEmpty(), List.copyOf(reasons), Map.copyOf(counts), train, val, test, trainLabels, valLabels, testLabels);
    }

    private static int count(List<AssignedRow> rows, DatasetSplit split) {
        return (int) rows.stream().filter(row -> row.split() == split).count();
    }

    private static int labels(List<AssignedRow> rows, DatasetSplit split) {
        return (int) rows.stream().filter(row -> row.split() == split).map(AssignedRow::label).distinct().count();
    }
}
