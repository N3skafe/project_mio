package lab.maidops.resolution;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ResolutionRequest(
        @NotBlank(message = "원인을 입력하세요.")
        @Size(max = 500, message = "원인은 500자 이하여야 합니다.")
        String cause,
        @NotBlank(message = "해결 방법을 입력하세요.")
        @Size(max = 500, message = "해결 방법은 500자 이하여야 합니다.")
        String method) {
}
