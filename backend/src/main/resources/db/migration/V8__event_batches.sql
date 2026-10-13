ALTER TABLE jobs
    ADD COLUMN log_storage_incomplete boolean NOT NULL DEFAULT false;

CREATE TABLE job_event_batches (
    job_id varchar(64) NOT NULL REFERENCES jobs (id),
    batch_id varchar(80) NOT NULL,
    payload_sha256 varchar(64) NOT NULL,
    line_count integer NOT NULL,
    created_at timestamptz NOT NULL,
    PRIMARY KEY (job_id, batch_id)
);

COMMENT ON TABLE job_event_batches IS
    '워커 로그 배치. 같은 batch_id와 같은 본문은 다시 저장하지 않습니다.';
COMMENT ON COLUMN jobs.log_storage_incomplete IS
    '프로세스가 끝났는지와 별개로, 서버가 확인하지 못한 로그 배치가 있습니다.';
