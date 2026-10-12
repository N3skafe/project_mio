package lab.maidops.job;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lab.maidops.domain.JobStatus;

@Entity
@Table(name = "jobs")
public class JobEntity {
    @Id
    @Column(length = 64)
    private String id;

    @Column(name = "project_id", nullable = false, length = 64)
    private String projectId;

    @Column(name = "task_id", nullable = false, length = 64)
    private String taskId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 32)
    private JobStatus status;

    @Column(name = "created_at", nullable = false)
    private Instant createdAt;

    @Column(name = "started_at")
    private Instant startedAt;

    @Column(name = "finished_at")
    private Instant finishedAt;

    @Column(name = "cancel_requested_at")
    private Instant cancelRequestedAt;

    @Column(name = "output_truncated", nullable = false)
    private boolean outputTruncated;

    @Column(name = "worker_id", length = 64)
    private String workerId;

    @Column(name = "lease_expires_at")
    private Instant leaseExpiresAt;

    @Column(name = "exit_code")
    private Integer exitCode;

    @Column(name = "cancel_confirmed_at")
    private Instant cancelConfirmedAt;

    public static JobEntity queued(String id, String projectId, String taskId, Instant createdAt) {
        JobEntity job = new JobEntity();
        job.id = id;
        job.projectId = projectId;
        job.taskId = taskId;
        job.status = JobStatus.QUEUED;
        job.createdAt = createdAt;
        job.outputTruncated = false;
        return job;
    }

    public String getId() {
        return id;
    }

    public String getProjectId() {
        return projectId;
    }

    public String getTaskId() {
        return taskId;
    }

    public JobStatus getStatus() {
        return status;
    }

    public void setStatus(JobStatus status) {
        this.status = status;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public void setStartedAt(Instant startedAt) {
        this.startedAt = startedAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }

    public void setFinishedAt(Instant finishedAt) {
        this.finishedAt = finishedAt;
    }

    public Instant getCancelRequestedAt() {
        return cancelRequestedAt;
    }

    public void setCancelRequestedAt(Instant cancelRequestedAt) {
        this.cancelRequestedAt = cancelRequestedAt;
    }

    public boolean isOutputTruncated() {
        return outputTruncated;
    }

    public void setOutputTruncated(boolean outputTruncated) {
        this.outputTruncated = outputTruncated;
    }

    public String getWorkerId() {
        return workerId;
    }

    public void setWorkerId(String workerId) {
        this.workerId = workerId;
    }

    public Instant getLeaseExpiresAt() {
        return leaseExpiresAt;
    }

    public void setLeaseExpiresAt(Instant leaseExpiresAt) {
        this.leaseExpiresAt = leaseExpiresAt;
    }

    public Integer getExitCode() {
        return exitCode;
    }

    public void setExitCode(Integer exitCode) {
        this.exitCode = exitCode;
    }

    public Instant getCancelConfirmedAt() {
        return cancelConfirmedAt;
    }

    public void setCancelConfirmedAt(Instant cancelConfirmedAt) {
        this.cancelConfirmedAt = cancelConfirmedAt;
    }
}
