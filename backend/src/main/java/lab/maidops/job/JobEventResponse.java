package lab.maidops.job;

import java.time.Instant;

public record JobEventResponse(int sequence, String text, Instant createdAt) {
    public static JobEventResponse from(JobEventEntity event) {
        return new JobEventResponse(event.getSequenceNo(), event.getText(), event.getCreatedAt());
    }
}
