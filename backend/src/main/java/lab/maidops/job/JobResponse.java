package lab.maidops.job;

import java.time.Instant;

import lab.maidops.domain.JobStatus;

public record JobResponse(
        String id,
        String projectId,
        String taskId,
        JobStatus status,
        Instant createdAt,
        Instant startedAt,
        Instant finishedAt,
        Instant cancelRequestedAt,
        boolean outputTruncated,
        Integer exitCode,
        String terminationReason,
        boolean logStorageIncomplete) {
    public static JobResponse from(JobEntity job) {
        return new JobResponse(
                job.getId(),
                job.getProjectId(),
                job.getTaskId(),
                job.getStatus(),
                job.getCreatedAt(),
                job.getStartedAt(),
                job.getFinishedAt(),
                job.getCancelRequestedAt(),
                job.isOutputTruncated(),
                job.getExitCode(),
                job.getTerminationReason(),
                job.isLogStorageIncomplete());
    }
}
