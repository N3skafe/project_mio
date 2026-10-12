package lab.maidops.lab;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TreeMap;
import java.util.regex.Pattern;

import lab.maidops.domain.DatasetSplit;
import lab.maidops.domain.ErrorLabel;

/**
 * 확정 사례를 그룹으로 묶고, 한 번 정한 테스트 그룹은 이후 학습으로 옮기지 않는다.
 */
public final class DatasetSplitter {
    private static final Pattern UUID = Pattern.compile(
            "\\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\\b");
    private static final Pattern PATH = Pattern.compile("([a-z]:\\\\[^\\s]+)|(/[^\\s]+)");
    private static final Pattern HEX = Pattern.compile("\\b[0-9a-f]{8,}\\b");
    private static final Pattern NUMBER = Pattern.compile("\\d+");
    private static final Pattern SPACE = Pattern.compile("\\s+");

    private DatasetSplitter() {
    }

    public record Row(String id, String jobId, String rawText, ErrorLabel label) {
    }

    public record AssignedRow(
            String id,
            String jobId,
            String rawText,
            ErrorLabel label,
            String templateHash,
            String groupKey,
            DatasetSplit split) {
    }

    public static String normalize(String text) {
        String value = text == null ? "" : text.toLowerCase(Locale.ROOT);
        value = UUID.matcher(value).replaceAll("<uuid>");
        value = PATH.matcher(value).replaceAll("<path>");
        value = HEX.matcher(value).replaceAll("<hex>");
        value = NUMBER.matcher(value).replaceAll("<n>");
        value = SPACE.matcher(value).replaceAll(" ").trim();
        if (value.length() > 500) {
            return value.substring(0, 500);
        }
        return value;
    }

    public static String templateHash(String text) {
        return sha256(normalize(text));
    }

    public static String sha256(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256을 사용할 수 없습니다.", exception);
        }
    }

    public static List<AssignedRow> assign(List<Row> rows, Map<String, DatasetSplit> anchors) {
        if (rows.isEmpty()) {
            return List.of();
        }
        int count = rows.size();
        int[] parent = new int[count];
        for (int index = 0; index < count; index++) {
            parent[index] = index;
        }
        Map<String, Integer> jobOwner = new LinkedHashMap<>();
        Map<String, Integer> templateOwner = new LinkedHashMap<>();
        String[] templates = new String[count];
        for (int index = 0; index < count; index++) {
            Row row = rows.get(index);
            templates[index] = templateHash(row.rawText());
            Integer jobSeen = jobOwner.putIfAbsent(row.jobId(), index);
            if (jobSeen != null) {
                union(parent, jobSeen, index);
            }
            Integer templateSeen = templateOwner.putIfAbsent(templates[index], index);
            if (templateSeen != null) {
                union(parent, templateSeen, index);
            }
        }

        Map<Integer, List<Integer>> members = new TreeMap<>();
        for (int index = 0; index < count; index++) {
            members.computeIfAbsent(find(parent, index), ignored -> new ArrayList<>()).add(index);
        }
        List<Component> components = new ArrayList<>();
        for (List<Integer> memberIndexes : members.values()) {
            memberIndexes.sort(Comparator.comparing(index -> rows.get(index).id()));
            List<String> templateList = memberIndexes.stream()
                    .map(index -> templates[index])
                    .distinct()
                    .sorted()
                    .toList();
            List<ErrorLabel> labels = memberIndexes.stream()
                    .map(index -> rows.get(index).label())
                    .distinct()
                    .sorted(Comparator.comparing(Enum::name))
                    .toList();
            components.add(new Component(memberIndexes, templateList, sha256(String.join("\n", templateList)), labels));
        }

        Map<Component, DatasetSplit> splits = new LinkedHashMap<>();
        if (anchors.isEmpty()) {
            assignStratified(components, splits);
        } else {
            for (Component component : components) {
                splits.put(component, inherit(component, anchors));
            }
        }

        List<AssignedRow> assigned = new ArrayList<>();
        for (Component component : components) {
            DatasetSplit split = splits.get(component);
            for (int index : component.members()) {
                Row row = rows.get(index);
                assigned.add(new AssignedRow(
                        row.id(),
                        row.jobId(),
                        row.rawText(),
                        row.label(),
                        templates[index],
                        component.groupKey(),
                        split));
            }
        }
        assigned.sort(Comparator.comparing(AssignedRow::id));
        return assigned;
    }

    public static String fingerprint(List<AssignedRow> rows) {
        List<String> lines = rows.stream()
                .sorted(Comparator.comparing(AssignedRow::id))
                .map(row -> row.id()
                        + "|"
                        + row.label().name()
                        + "|"
                        + row.split().name()
                        + "|"
                        + row.groupKey()
                        + "|"
                        + sha256(row.rawText()))
                .toList();
        return sha256(String.join("\n", lines));
    }

    private static void assignStratified(List<Component> components, Map<Component, DatasetSplit> splits) {
        Map<String, List<Component>> byLabel = new TreeMap<>();
        for (Component component : components) {
            String stratum = component.labels().get(0).name();
            byLabel.computeIfAbsent(stratum, ignored -> new ArrayList<>()).add(component);
        }
        for (List<Component> group : byLabel.values()) {
            group.sort(Comparator.comparing(Component::groupKey));
            for (int index = 0; index < group.size(); index++) {
                int slot = index % 5;
                DatasetSplit split = slot == 0 ? DatasetSplit.TEST : slot == 1 ? DatasetSplit.VAL : DatasetSplit.TRAIN;
                splits.put(group.get(index), split);
            }
        }
    }

    private static DatasetSplit inherit(Component component, Map<String, DatasetSplit> anchors) {
        DatasetSplit inherited = null;
        for (String template : component.templates()) {
            DatasetSplit anchored = anchors.get(template);
            if (anchored != null && (inherited == null || anchored.holdoutRank() > inherited.holdoutRank())) {
                inherited = anchored;
            }
        }
        return inherited == null ? DatasetSplit.TRAIN : inherited;
    }

    private static int find(int[] parent, int index) {
        int cursor = index;
        while (parent[cursor] != cursor) {
            parent[cursor] = parent[parent[cursor]];
            cursor = parent[cursor];
        }
        return cursor;
    }

    private static void union(int[] parent, int left, int right) {
        int leftRoot = find(parent, left);
        int rightRoot = find(parent, right);
        if (leftRoot != rightRoot) {
            parent[rightRoot] = leftRoot;
        }
    }

    private record Component(List<Integer> members, List<String> templates, String groupKey, List<ErrorLabel> labels) {
    }
}
