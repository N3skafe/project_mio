ALTER TABLE jobs ADD COLUMN termination_reason varchar(64);

ALTER TABLE jobs
    ADD CONSTRAINT jobs_termination_reason_ck CHECK (
        termination_reason IS NULL
        OR termination_reason IN (
            'COMPLETED',
            'FAILED',
            'TIMED_OUT',
            'CANCELLED',
            'OUTPUT_LIMIT_EXCEEDED',
            'SUPERVISION_FAILED'
        )
    );

COMMENT ON COLUMN jobs.termination_reason IS
    '워커가 프로세스를 끝낸 이유. output_truncated의 보관 줄 수 제한과는 별개입니다.';
