package lab.maidops.job;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class IdAllocator {
    private final JdbcTemplate jdbcTemplate;

    public IdAllocator(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public String nextJobId() {
        return format("job_id_seq", "job-");
    }

    public String nextErrorCaseId() {
        return format("error_case_id_seq", "case-");
    }

    public String nextResolutionId() {
        return format("resolution_id_seq", "resolution-");
    }

    public String nextTrainingRunId() {
        return format("training_run_id_seq", "run-");
    }

    public String nextModelVersionId() {
        return format("model_version_id_seq", "mv-");
    }

    public String nextDraftInferenceId() {
        return format("draft_inference_id_seq", "inf-");
    }

    private String format(String sequence, String prefix) {
        Long value = jdbcTemplate.queryForObject("select nextval('" + sequence + "')", Long.class);
        if (value == null) {
            throw new IllegalStateException("sequence " + sequence + " returned null");
        }
        return prefix + String.format("%08d", value);
    }
}
