package lab.maidops.project;

import java.util.List;

public record CreateTaskRequest(
        String id,
        String name,
        String planText,
        List<String> argvJson,
        String relativeWorkdir,
        Integer timeoutSeconds) {
}
