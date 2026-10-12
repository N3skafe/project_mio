package lab.maidops.project;

import java.util.List;

public record ProjectResponse(String id, String name, String summary, String defaultTaskId) {
    public static ProjectResponse from(ProjectEntity entity) {
        return new ProjectResponse(entity.getId(), entity.getName(), entity.getSummary(), entity.getDefaultTaskId());
    }
}

record TaskResponse(String id, String projectId, String name, String planText) {
    static TaskResponse from(RegisteredTaskEntity entity) {
        return new TaskResponse(entity.getId(), entity.getProjectId(), entity.getName(), entity.getPlanText());
    }
}

record TaskListResponse(List<TaskResponse> items) {
}
