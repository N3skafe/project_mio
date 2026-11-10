package lab.maidops.errorcase;

import java.util.List;

public record ImportLogRequest(
        String projectId,
        String rawLog,
        List<String> lines,
        String sourceHint,
        String title) {
}
