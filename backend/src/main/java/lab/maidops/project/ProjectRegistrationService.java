package lab.maidops.project;

import java.nio.file.Path;
import java.util.List;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lab.maidops.api.ApiException;
import lab.maidops.worker.RegisteredCommandResolver;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class ProjectRegistrationService {
    static final String ID_PATTERN = "^[a-z][a-z0-9-]{1,62}$";
    private static final String TRUST =
            "신뢰하는 workspace 안의 등록 명령만 실행합니다. 임의 셸은 실행하지 않습니다.";

    private final ProjectRepository projects;
    private final RegisteredTaskRepository tasks;
    private final RegisteredCommandResolver commands;
    private final ObjectMapper objectMapper;
    private final String workspaceRoot;

    public ProjectRegistrationService(
            ProjectRepository projects,
            RegisteredTaskRepository tasks,
            RegisteredCommandResolver commands,
            ObjectMapper objectMapper,
            @Value("${maidops.workspace-root:}") String workspaceRoot) {
        this.projects = projects;
        this.tasks = tasks;
        this.commands = commands;
        this.objectMapper = objectMapper;
        this.workspaceRoot = workspaceRoot;
    }

    @Transactional
    public ProjectResponse createProject(CreateProjectRequest request) {
        if (request == null) {
            throw new ApiException(400, "VALIDATION", "프로젝트 본문이 없습니다.", "{\"id\":\"my-api\",\"name\":\"내 API\"}");
        }
        String id = requiredId(request.id(), "프로젝트 id");
        String name = requiredText(request.name(), "이름", 120, "내 API");
        if (projects.existsById(id)) {
            throw new ApiException(409, "STATE", "이미 등록된 프로젝트입니다: " + id, id);
        }
        String summary = request.summary() == null || request.summary().isBlank()
                ? "사용자가 등록한 프로젝트입니다. " + TRUST
                : requiredText(request.summary(), "설명", 500, TRUST);
        ProjectEntity project = new ProjectEntity();
        project.setId(id);
        project.setName(name);
        project.setSummary(summary);
        project.setDefaultTaskId(null);
        return ProjectResponse.from(projects.save(project));
    }

    @Transactional
    public TaskResponse createTask(String projectId, CreateTaskRequest request) {
        ProjectEntity project = projects.findById(projectId)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "프로젝트를 찾지 못했습니다: " + projectId, "/project list"));
        if (request == null) {
            throw new ApiException(400, "VALIDATION", "작업 본문이 없습니다.", "{\"id\":\"my-check\",\"argv_json\":[\"{python}\",\"pass_check.py\"]}");
        }
        String id = requiredId(request.id(), "작업 id");
        if (tasks.existsById(id)) {
            throw new ApiException(409, "STATE", "작업 id는 전체에서 유일합니다. 이미 등록된 id입니다: " + id, id);
        }
        String name = requiredText(request.name(), "이름", 120, "통과 점검");
        String plan = requiredText(request.planText(), "계획", 1000, "등록된 {python} 스크립트를 실행합니다.");
        if (request.timeoutSeconds() == null || request.timeoutSeconds() < 1 || request.timeoutSeconds() > 120) {
            throw new ApiException(400, "VALIDATION", "timeout_seconds는 1 이상 120 이하여야 합니다.", "10");
        }
        if (request.relativeWorkdir() == null || request.relativeWorkdir().isBlank()) {
            throw new ApiException(400, "VALIDATION", "relative_workdir가 없습니다. workspace 루트 기준 상대 경로만 허용합니다.", "sample");
        }
        if (request.argvJson() == null || request.argvJson().isEmpty()) {
            throw new ApiException(400, "VALIDATION", "argv_json은 문자열 배열이어야 합니다. 첫 토큰은 {python}만 허용합니다.", "[\"{python}\",\"pass_check.py\"]");
        }
        if (workspaceRoot == null || workspaceRoot.isBlank()) {
            throw new ApiException(
                    400,
                    "VALIDATION",
                    "MAIDOPS_WORKSPACE_ROOT가 없으면 작업을 등록할 수 없습니다. " + TRUST,
                    "sample");
        }
        String argvJson = writeArgv(request.argvJson());
        RegisteredTaskEntity probe = new RegisteredTaskEntity();
        probe.setId(id);
        probe.setProjectId(project.getId());
        probe.setName(name);
        probe.setPlanText(plan);
        probe.setArgvJson(argvJson);
        probe.setRelativeWorkdir(request.relativeWorkdir().trim());
        probe.setTimeoutSeconds(request.timeoutSeconds());
        RegisteredCommandResolver.Resolved resolved = commands.resolve(Path.of(workspaceRoot), probe);
        if (!resolved.accepted()) {
            throw new ApiException(400, "VALIDATION", resolved.reason() + " " + TRUST, "sample");
        }
        tasks.save(probe);
        if (project.getDefaultTaskId() == null) {
            project.setDefaultTaskId(id);
        }
        return TaskResponse.from(probe);
    }

    private String writeArgv(List<String> argv) {
        try {
            return objectMapper.writeValueAsString(argv);
        } catch (JsonProcessingException exception) {
            throw new ApiException(400, "VALIDATION", "argv_json을 저장하지 못했습니다.", "[\"{python}\",\"pass_check.py\"]");
        }
    }

    private static String requiredId(String value, String label) {
        String id = requiredText(value, label, 64, "my-api");
        if (!id.matches(ID_PATTERN)) {
            throw new ApiException(
                    400,
                    "VALIDATION",
                    label + "는 소문자, 숫자, 하이픈만 쓰고 2자 이상 63자 이하여야 합니다.",
                    "my-api");
        }
        return id;
    }

    private static String requiredText(String value, String label, int limit, String example) {
        if (value == null || value.isBlank()) {
            throw new ApiException(400, "VALIDATION", label + "이 없습니다.", example);
        }
        String trimmed = value.trim();
        if (trimmed.length() > limit) {
            throw new ApiException(400, "VALIDATION", label + "은 " + limit + "자 이하여야 합니다.", example);
        }
        return trimmed;
    }
}
