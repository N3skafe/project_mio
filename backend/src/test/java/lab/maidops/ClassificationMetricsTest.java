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
