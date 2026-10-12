package lab.maidops.lab;

import java.util.ArrayList;
import java.util.List;

import lab.maidops.domain.ErrorLabel;

/**
 * 테스트 분할의 혼동행렬로 macro F1과 클래스별 점수를 계산한다.
 * 지원 사례가 없는 클래스의 F1은 null이며 macro 평균에 넣지 않는다.
 */
public final class ClassificationMetrics {
    public static final List<ErrorLabel> LABELS = List.of(ErrorLabel.values());

    private ClassificationMetrics() {
    }

    public record ClassScore(ErrorLabel label, Double precision, Double recall, Double f1, int support) {
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
        List<ClassScore> scores = new ArrayList<>();
        List<Double> included = new ArrayList<>();
        for (int row = 0; row < size; row++) {
            int truePositive = matrix[row][row];
            Double precision = predicted[row] == 0 ? null : (double) truePositive / predicted[row];
            Double recall = support[row] == 0 ? null : (double) truePositive / support[row];
            Double f1 = null;
            if (precision != null && recall != null) {
                double denominator = precision + recall;
                f1 = denominator == 0.0 ? 0.0 : (2.0 * precision * recall) / denominator;
            }
            if (support[row] > 0 && f1 != null) {
                included.add(f1);
            }
            scores.add(new ClassScore(LABELS.get(row), precision, recall, f1, support[row]));
        }
        if (included.size() < TrainingPolicy.MIN_LABELS_IN_TEST) {
            throw new IllegalArgumentException("macro F1을 계산할 테스트 클래스가 2개 미만입니다.");
        }
        double macro = included.stream().mapToDouble(Double::doubleValue).average().orElseThrow();
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
            if (actual.label() != wanted.label() || actual.support() != wanted.support()) {
                throw new IllegalArgumentException("클래스별 지원 건수가 혼동행렬과 일치하지 않습니다.");
            }
            if (!close(actual.precision(), wanted.precision())
                    || !close(actual.recall(), wanted.recall())
                    || !close(actual.f1(), wanted.f1())) {
                throw new IllegalArgumentException("클래스별 점수가 혼동행렬과 일치하지 않습니다.");
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
