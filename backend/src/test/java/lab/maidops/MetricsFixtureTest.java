package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.assertj.core.api.Assertions.within;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.lab.ClassificationMetrics;
import lab.maidops.lab.ClassificationMetrics.ClassScore;
import lab.maidops.lab.ClassificationMetrics.Report;
import org.junit.jupiter.api.Test;

class MetricsFixtureTest {
    @Test
    void sharedFixtureMatchesJavaMetrics() throws Exception {
        Path path = Path.of("contracts", "metrics", "supported-class-macro-f1-v2.json");
        if (!Files.exists(path)) {
            path = Path.of("..", "contracts", "metrics", "supported-class-macro-f1-v2.json");
        }
        JsonNode document = new ObjectMapper().readTree(path.toFile());
        assertThat(document.get("metric_policy").asText()).isEqualTo(ClassificationMetrics.METRIC_POLICY);
        assertThat(document.get("row_meaning").asText()).isEqualTo("actual");
        assertThat(document.get("column_meaning").asText()).isEqualTo("predicted");
        List<String> order = new ArrayList<>();
        document.get("label_order").forEach(node -> order.add(node.asText()));
        assertThat(order).containsExactly("DB_CONNECTION", "AUTH_PERMISSION", "EXTERNAL_NETWORK", "INPUT_VALIDATION", "OTHER");
        for (JsonNode item : document.get("cases")) {
            int[][] matrix = matrix(item.get("matrix"));
            if ("label-order".equals(text(item, "error"))) {
                Report report = ClassificationMetrics.fromConfusion(matrix);
                List<ClassScore> swapped = new ArrayList<>();
                for (JsonNode label : item.get("submitted_label_order")) {
                    ErrorLabel wanted = ErrorLabel.valueOf(label.asText());
                    swapped.add(report.perClass().stream()
                            .filter(score -> score.label() == wanted)
                            .findFirst()
                            .orElseThrow());
                }
                assertThatThrownBy(() -> ClassificationMetrics.assertMatches(
                        report,
                        new ClassificationMetrics.Submitted(report.macroF1(), swapped)))
                        .isInstanceOf(IllegalArgumentException.class);
                continue;
            }
            if (item.hasNonNull("error")) {
                assertThatThrownBy(() -> ClassificationMetrics.fromConfusion(matrix))
                        .isInstanceOf(IllegalArgumentException.class);
                continue;
            }
            Report report = ClassificationMetrics.fromConfusion(matrix);
            assertThat(report.macroF1()).isCloseTo(number(item.get("macro_f1")), within(1e-9));
            int support = report.perClass().stream().mapToInt(ClassScore::support).sum();
            assertThat(support).isEqualTo(item.get("evaluation_sample_count").asInt());
            List<String> included = report.perClass().stream()
                    .filter(ClassScore::includedInMacro)
                    .map(score -> score.label().name())
                    .toList();
            List<String> expectedIncluded = new ArrayList<>();
            item.get("included_labels").forEach(node -> expectedIncluded.add(node.asText()));
            assertThat(included).isEqualTo(expectedIncluded);
            if (item.has("per_class")) {
                for (JsonNode expected : item.get("per_class")) {
                    ClassScore actual = report.perClass().stream()
                            .filter(score -> score.label() == ErrorLabel.valueOf(expected.get("label").asText()))
                            .findFirst()
                            .orElseThrow();
                    assertThat(actual.support()).isEqualTo(expected.get("support").asInt());
                    assertThat(actual.predictedCount()).isEqualTo(expected.get("predicted_count").asInt());
                    assertThat(actual.falsePositives()).isEqualTo(expected.get("false_positives").asInt());
                    assertThat(actual.includedInMacro()).isEqualTo(expected.get("included_in_macro").asBoolean());
                    assertClose(actual.precision(), number(expected.get("precision")));
                    assertClose(actual.recall(), number(expected.get("recall")));
                    assertClose(actual.f1(), number(expected.get("f1")));
                }
            }
        }
    }

    private static int[][] matrix(JsonNode rows) {
        int[][] matrix = new int[rows.size()][];
        for (int row = 0; row < rows.size(); row++) {
            JsonNode values = rows.get(row);
            matrix[row] = new int[values.size()];
            for (int column = 0; column < values.size(); column++) {
                matrix[row][column] = values.get(column).asInt();
            }
        }
        return matrix;
    }

    private static void assertClose(Double actual, Double expected) {
        if (expected == null) {
            assertThat(actual).isNull();
            return;
        }
        assertThat(actual).isCloseTo(expected, within(1e-9));
    }

    private static Double number(JsonNode node) {
        if (node == null || node.isNull()) {
            return null;
        }
        String text = node.asText();
        if (text.contains("/")) {
            String[] parts = text.split("/");
            return Double.parseDouble(parts[0]) / Double.parseDouble(parts[1]);
        }
        return node.asDouble();
    }

    private static String text(JsonNode node, String field) {
        JsonNode value = node.get(field);
        return value == null || value.isNull() ? null : value.asText();
    }
}
