package lab.maidops.errorcase;

import lab.maidops.domain.ErrorLabel;
import lab.maidops.domain.ReviewDecision;
import jakarta.validation.constraints.NotNull;

public record ReviewRequest(
        @NotNull(message = "decision이 필요합니다.") ReviewDecision decision,
        ErrorLabel label) {
}
