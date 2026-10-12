package lab.maidops.project;

import java.util.List;

import lab.maidops.api.ApiException;
import lab.maidops.api.PageResponse;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/projects")
public class ProjectController {
    private final ProjectRepository projects;
    private final RegisteredTaskRepository tasks;

    public ProjectController(ProjectRepository projects, RegisteredTaskRepository tasks) {
        this.projects = projects;
        this.tasks = tasks;
    }

    @GetMapping
    public PageResponse<ProjectResponse> list() {
        List<ProjectResponse> items = projects.findAll().stream()
                .sorted((left, right) -> left.getId().compareTo(right.getId()))
                .map(ProjectResponse::from)
                .toList();
        return new PageResponse<>(items, null);
    }

    @GetMapping("/{id}")
    public ProjectResponse get(@PathVariable String id) {
        return projects.findById(id)
                .map(ProjectResponse::from)
                .orElseThrow(() -> new ApiException(404, "NOT_FOUND", "프로젝트를 찾지 못했습니다: " + id, "/project list"));
    }

    @GetMapping("/{id}/tasks")
    public TaskListResponse tasks(@PathVariable String id) {
        if (!projects.existsById(id)) {
            throw new ApiException(404, "NOT_FOUND", "프로젝트를 찾지 못했습니다: " + id, "/project list");
        }
        List<TaskResponse> items = tasks.findByProjectIdOrderByIdAsc(id).stream().map(TaskResponse::from).toList();
        return new TaskListResponse(items);
    }
}
