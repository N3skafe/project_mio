package lab.maidops.job;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record CreateJobRequest(
        @NotBlank(message = "project_id가 필요합니다.")
        @Pattern(regexp = "^[a-z0-9-]{1,64}$", message = "project_id 형식이 올바르지 않습니다.")
        String projectId,
        @NotBlank(message = "task_id가 필요합니다.")
        @Pattern(regexp = "^[a-z0-9-]{1,64}$", message = "task_id 형식이 올바르지 않습니다.")
        String taskId) {
}
