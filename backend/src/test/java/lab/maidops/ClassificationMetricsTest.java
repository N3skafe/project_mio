package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import lab.maidops.domain.ErrorLabel;
import lab.maidops.lab.ClassificationMetrics;
import lab.maidops.lab.ClassificationMetrics.ClassScore;
import lab.maidops.lab.ClassificationMetrics.Report;
import org.junit.jupiter.api.Test;

class ClassificationMetricsTest {
    @Test
    void macroF1UsesOnlyClassesThatHaveSupport() {
        Report report = ClassificationMetrics.fromConfusion(new int[][] {
                {2, 0, 0, 0, 0},
                {0, 1, 1, 0, 0},
                {0, 0, 0, 0, 0},
                {0, 0, 0, 1, 0},
                {1, 0, 0, 0, 1}
        });
        ClassScore external = report.perClass().get(2);
        assertThat(external.label()).isEqualTo(ErrorLabel.EXTERNAL_NETWORK);
        assertThat(external.support()).isZero();
        assertThat(external.f1()).isNull();
        assertThat(external.recall()).isNull();
        assertThat(external.precision()).isEqualTo(0.0);
        assertThat(report.perClass().get(0).f1()).isEqualTo(0.8);
        assertThat(report.macroF1()).isEqualTo(47.0 / 60.0);
        ClassificationMetrics.assertMatches(
                report,
                new ClassificationMetrics.Submitted(report.macroF1(), report.perClass()));
    }

    @Test
    void supportedClassWithNoPredictionsLowersMacroF1() {
        Report report = ClassificationMetrics.fromConfusion(new int[][] {
                {2, 0, 0, 0, 0},
                {0, 2, 0, 0, 0},
                {0, 0, 0, 0, 0},
                {0, 0, 2, 0, 0},
                {0, 0, 0, 0, 0}
        });
        ClassScore input = report.perClass().get(3);
        assertThat(input.label()).isEqualTo(ErrorLabel.INPUT_VALIDATION);
        assertThat(input.support()).isEqualTo(2);
        assertThat(input.predictedCount()).isZero();
        assertThat(input.precision()).isEqualTo(0.0);
        assertThat(input.recall()).isEqualTo(0.0);
        assertThat(input.f1()).isEqualTo(0.0);
        assertThat(input.includedInMacro()).isTrue();
        assertThat(report.perClass().get(2).f1()).isNull();
        assertThat(report.macroF1()).isEqualTo(2.0 / 3.0);
    }

    @Test
    void aMismatchedScoreIsRejected() {
        Report report = ClassificationMetrics.fromConfusion(new int[][] {
                {1, 0, 0, 0, 0},
                {0, 1, 0, 0, 0},
                {0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0},
                {0, 0, 0, 0, 0}
        });
        assertThatThrownBy(() -> ClassificationMetrics.assertMatches(
                report,
                new ClassificationMetrics.Submitted(0.91, report.perClass())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("macro F1");
    }
}
