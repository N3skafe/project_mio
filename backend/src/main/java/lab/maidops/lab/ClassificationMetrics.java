package lab.maidops.lab;

import java.util.ArrayList;
import java.util.List;

import lab.maidops.domain.ErrorLabel;

/**
 * 정책 supported-class-macro-f1-v2.
 * 행은 실제 라벨, 열은 예측 라벨이다.
 * support가 0보다 크면 macro에 포함하고, 예측이 없으면 precision·recall·F1은 0이다.
 * support가 0이면 macro에서 뺀다. 예측만 있으면 precision은 0이고 recall과 F1은 null이다.
 */
public final class ClassificationMetrics {
    public static final String METRIC_POLICY = "supported-class-macro-f1-v2";
    public static final List<ErrorLabel> LABELS = List.of(ErrorLabel.values());

    private ClassificationMetrics() {
    }

    public record ClassScore(
            ErrorLabel label,
            Double precision,
            Double recall,
            Double f1,
            int support,
            int predictedCount,
            int falsePositives,
            boolean includedInMacro) {
    }

    public record Report(double macroF1, List<ClassScore> perClass, int[][] confusion) {
    }

    public static Report fromConfusion(int[][] matrix) {
        int size = LABELS.size();
        if (matrix.length != size) {
            throw new IllegalArgumentException("혼동행렬은 라벨 수와 같은 정사각 행렬이어야 합니다.");
        }
        int[] support = new int[size];
        int[] predicted = new int[size];
        for (int row = 0; row < size; row++) {
            if (matrix[row].length != size) {
                throw new IllegalArgumentException("혼동행렬은 라벨 수와 같은 정사각 행렬이어야 합니다.");
            }
            for (int column = 0; column < size; column++) {
                if (matrix[row][column] < 0) {
                    throw new IllegalArgumentException("혼동행렬에는 음수를 넣을 수 없습니다.");
                }
                support[row] += matrix[row][column];
                predicted[column] += matrix[row][column];
            }
        }
        if (sum(support) == 0) {
            throw new IllegalArgumentException("실제 표본이 없어 macro F1을 계산할 수 없습니다. 점수를 만들지 않습니다.");
        }
        List<ClassScore> scores = new ArrayList<>();
        List<Double> included = new ArrayList<>();
        for (int row = 0; row < size; row++) {
            int truePositive = matrix[row][row];
            int falsePositives = predicted[row] - truePositive;
            if (support[row] > 0) {
                double recall = (double) truePositive / support[row];
                double precision = predicted[row] == 0 ? 0.0 : (double) truePositive / predicted[row];
                double f1 = f1(precision, recall);
                requireFinite(precision, recall, f1);
                included.add(f1);
                scores.add(new ClassScore(
                        LABELS.get(row), precision, recall, f1, support[row], predicted[row], falsePositives, true));
            } else {
                Double precision = predicted[row] == 0 ? null : 0.0;
                if (precision != null) {
                    requireFinite(precision);
                }
                scores.add(new ClassScore(
                        LABELS.get(row), precision, null, null, 0, predicted[row], falsePositives, false));
            }
        }
        if (included.size() < TrainingPolicy.MIN_LABELS_IN_TEST) {
            throw new IllegalArgumentException("macro F1을 계산할 실제 표본 클래스가 2개 미만입니다. 점수를 만들지 않습니다.");
        }
        double macro = included.stream().mapToDouble(Double::doubleValue).average().orElseThrow();
        requireFinite(macro);
        return new Report(macro, List.copyOf(scores), copy(matrix));
    }

    public static void assertMatches(Report expected, Submitted submitted) {
        if (!close(submitted.macroF1(), expected.macroF1())) {
            throw new IllegalArgumentException("macro F1이 혼동행렬과 일치하지 않습니다.");
        }
        if (submitted.perClass().size() != expected.perClass().size()) {
            throw new IllegalArgumentException("클래스별 점수 개수가 라벨 수와 다릅니다.");
        }
        for (int index = 0; index < expected.perClass().size(); index++) {
            ClassScore actual = submitted.perClass().get(index);
            ClassScore wanted = expected.perClass().get(index);
            if (actual.label() != wanted.label()
                    || actual.support() != wanted.support()
                    || actual.predictedCount() != wanted.predictedCount()
                    || actual.falsePositives() != wanted.falsePositives()
                    || actual.includedInMacro() != wanted.includedInMacro()) {
                throw new IllegalArgumentException("클래스별 지원 건수가 혼동행렬과 일치하지 않습니다.");
            }
            if (!close(actual.precision(), wanted.precision())
                    || !close(actual.recall(), wanted.recall())
                    || !close(actual.f1(), wanted.f1())) {
                throw new IllegalArgumentException("클래스별 점수가 혼동행렬과 일치하지 않습니다.");
            }
        }
    }

    private static int sum(int[] values) {
        int total = 0;
        for (int value : values) {
            total += value;
        }
        return total;
    }

    private static double f1(double precision, double recall) {
        double denominator = precision + recall;
        if (denominator == 0.0) {
            return 0.0;
        }
        return (2.0 * precision * recall) / denominator;
    }

    private static void requireFinite(double... values) {
        for (double value : values) {
            if (!Double.isFinite(value)) {
                throw new IllegalArgumentException("평가 점수가 유한하지 않습니다. 점수를 만들지 않습니다.");
            }
        }
    }

    private static boolean close(double actual, double expected) {
        return Double.isFinite(actual) && Math.abs(actual - expected) <= 1.0e-4;
    }

    private static boolean close(Double actual, Double expected) {
        if (actual == null || expected == null) {
            return actual == null && expected == null;
        }
        return Double.isFinite(actual) && Math.abs(actual - expected) <= 1.0e-4;
    }

    private static int[][] copy(int[][] matrix) {
        int[][] copied = new int[matrix.length][];
        for (int index = 0; index < matrix.length; index++) {
            copied[index] = matrix[index].clone();
        }
        return copied;
    }

    public record Submitted(double macroF1, List<ClassScore> perClass) {
    }
}
