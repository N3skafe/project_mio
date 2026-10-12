package lab.maidops.worker;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lab.maidops.project.RegisteredTaskEntity;
import org.springframework.stereotype.Component;

@Component
public class RegisteredCommandResolver {
    private static final TypeReference<List<String>> STRING_LIST = new TypeReference<>() {
    };

    private final ObjectMapper objectMapper;

    public RegisteredCommandResolver(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public Resolved resolve(Path workspaceRoot, RegisteredTaskEntity task) {
        if (workspaceRoot == null) {
            return Resolved.rejected("MAIDOPS_WORKSPACE_ROOT가 설정되지 않았습니다.");
        }
        Path root = workspaceRoot.toAbsolutePath().normalize();
        if (!root.toFile().isDirectory()) {
            return Resolved.rejected("허용된 작업 디렉터리가 없습니다: " + root);
        }
        if (task.getArgvJson() == null || task.getRelativeWorkdir() == null) {
            return Resolved.rejected("등록된 argv가 없습니다.");
        }
        Path relative = Path.of(task.getRelativeWorkdir());
        if (relative.isAbsolute() || relative.normalize().startsWith("..")) {
            return Resolved.rejected("작업 디렉터리가 허용 경로 밖입니다.");
        }
        for (Path part : relative) {
            if ("..".equals(part.toString())) {
                return Resolved.rejected("작업 디렉터리가 허용 경로 밖입니다.");
            }
        }
        Path workdir = root.resolve(relative).normalize();
        if (!workdir.startsWith(root) || !workdir.toFile().isDirectory()) {
            return Resolved.rejected("작업 디렉터리를 찾지 못했습니다: " + workdir);
        }
        List<String> argv;
        try {
            argv = objectMapper.readValue(task.getArgvJson(), STRING_LIST);
        } catch (Exception exception) {
            return Resolved.rejected("argv JSON을 읽지 못했습니다.");
        }
        if (argv.size() < 2 || argv.size() > 8) {
            return Resolved.rejected("argv 길이가 허용 범위가 아닙니다.");
        }
        if (!"{python}".equals(argv.get(0))) {
            return Resolved.rejected("실행 파일은 {python} 토큰만 허용합니다.");
        }
        for (String arg : argv) {
            if (arg == null || arg.isBlank() || arg.indexOf('\n') >= 0 || arg.indexOf('\0') >= 0) {
                return Resolved.rejected("argv에 빈 값이나 제어 문자가 있습니다.");
            }
            if (arg.contains("&&") || arg.contains("||") || arg.contains("|") || arg.contains(">") || arg.contains("<")) {
                return Resolved.rejected("argv에 셸 연산자가 있습니다.");
            }
        }
        Path script = workdir.resolve(argv.get(1)).normalize();
        if (!script.startsWith(root) || !script.toFile().isFile()) {
            return Resolved.rejected("스크립트가 허용 경로 안에 없습니다: " + argv.get(1));
        }
        List<String> resolved = new ArrayList<>();
        resolved.add("{python}");
        resolved.add(script.toString());
        for (int index = 2; index < argv.size(); index++) {
            resolved.add(argv.get(index));
        }
        int timeout = task.getTimeoutSeconds() == null ? 10 : task.getTimeoutSeconds();
        if (timeout < 1 || timeout > 120) {
            return Resolved.rejected("timeout_seconds는 1 이상 120 이하여야 합니다.");
        }
        return Resolved.accepted(resolved, workdir.toString(), timeout);
    }

    public record Resolved(boolean accepted, String reason, List<String> argv, String workingDirectory, int timeoutSeconds) {
        static Resolved rejected(String reason) {
            return new Resolved(false, reason, List.of(), "", 0);
        }

        static Resolved accepted(List<String> argv, String workingDirectory, int timeoutSeconds) {
            return new Resolved(true, "", argv, workingDirectory, timeoutSeconds);
        }
    }
}
