package lab.maidops;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import lab.maidops.domain.DatasetSplit;
import lab.maidops.domain.ErrorLabel;
import lab.maidops.lab.DatasetSplitter;
import lab.maidops.lab.DatasetSplitter.AssignedRow;
import lab.maidops.lab.DatasetSplitter.Row;
import lab.maidops.lab.TrainingPolicy;
import org.junit.jupiter.api.Test;

class DatasetSplitterTest {
    private static final String[] WORDS = {
            "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
            "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
            "quebec", "romeo", "sierra", "tango"
    };

    @Test
    void numbersAndTheSameJobStayInOneGroup() {
        assertThat(DatasetSplitter.templateHash("port 1111 down"))
                .isEqualTo(DatasetSplitter.templateHash("port 2222 down"));
        List<AssignedRow> assigned = DatasetSplitter.assign(List.of(
                new Row("case-a", "job-1", "disk full on alpha", ErrorLabel.OTHER),
                new Row("case-b", "job-1", "timeout on beta", ErrorLabel.EXTERNAL_NETWORK)), Map.of());
        assertThat(assigned).hasSize(2);
        assertThat(assigned.get(0).groupKey()).isEqualTo(assigned.get(1).groupKey());
        assertThat(assigned.get(0).split()).isEqualTo(assigned.get(1).split());
    }

    @Test
    void firstSplitMeetsTheGateAndStaysFixed() {
        List<Row> rows = new ArrayList<>();
        for (int index = 0; index < WORDS.length; index++) {
            ErrorLabel label = index % 2 == 0 ? ErrorLabel.DB_CONNECTION : ErrorLabel.AUTH_PERMISSION;
            rows.add(new Row("case-" + index, "job-" + index, "unique failure token " + WORDS[index] + " end", label));
        }
        List<AssignedRow> first = DatasetSplitter.assign(rows, Map.of());
        TrainingPolicy.Gate gate = TrainingPolicy.evaluate(first, 1, 1);
        assertThat(gate.eligible()).isTrue();
        assertThat(gate.reasons()).isEmpty();
        assertThat(count(first, DatasetSplit.TRAIN)).isEqualTo(12);
        assertThat(count(first, DatasetSplit.VAL)).isEqualTo(4);
        assertThat(count(first, DatasetSplit.TEST)).isEqualTo(4);
        assertThat(labels(first, DatasetSplit.TRAIN)).isGreaterThanOrEqualTo(2);
        assertThat(labels(first, DatasetSplit.TEST)).isGreaterThanOrEqualTo(2);
        assertThat(crosses(first)).isFalse();

        Map<String, DatasetSplit> anchors = new LinkedHashMap<>();
        for (AssignedRow row : first) {
            anchors.put(row.templateHash(), row.split());
        }
        List<Row> again = new ArrayList<>(rows);
        again.add(new Row("case-new", "job-new", "unique failure token uniform end", ErrorLabel.OTHER));
        List<AssignedRow> second = DatasetSplitter.assign(again, anchors);
        for (AssignedRow original : first) {
            AssignedRow matched = second.stream()
                    .filter(row -> row.id().equals(original.id()))
                    .findFirst()
                    .orElseThrow();
            assertThat(matched.split()).isEqualTo(original.split());
        }
        AssignedRow added = second.stream().filter(row -> row.id().equals("case-new")).findFirst().orElseThrow();
        assertThat(added.split()).isEqualTo(DatasetSplit.TRAIN);
        assertThat(crosses(second)).isFalse();
    }

    @Test
    void tooFewConfirmedCasesAreNotEligible() {
        List<AssignedRow> rows = DatasetSplitter.assign(List.of(
                new Row("case-1", "job-1", "unique failure token alpha end", ErrorLabel.OTHER)), Map.of());
        TrainingPolicy.Gate gate = TrainingPolicy.evaluate(rows, 2, 1);
        assertThat(gate.eligible()).isFalse();
        assertThat(String.join(" ", gate.reasons())).contains("확정 사례가 1건").contains("학습 수에 넣지 않았습니다");
    }

    private static int count(List<AssignedRow> rows, DatasetSplit split) {
        return (int) rows.stream().filter(row -> row.split() == split).count();
    }

    private static int labels(List<AssignedRow> rows, DatasetSplit split) {
        return (int) rows.stream().filter(row -> row.split() == split).map(AssignedRow::label).distinct().count();
    }

    private static boolean crosses(List<AssignedRow> rows) {
        Map<String, DatasetSplit> seen = new LinkedHashMap<>();
        for (AssignedRow row : rows) {
            DatasetSplit previous = seen.putIfAbsent(row.groupKey(), row.split());
            if (previous != null && previous != row.split()) {
                return true;
            }
        }
        return false;
    }
}
