ALTER TABLE training_runs
    ADD COLUMN status varchar(32),
    ADD COLUMN dataset_fingerprint varchar(64),
    ADD COLUMN label_schema_version varchar(64),
    ADD COLUMN embedding_id varchar(120),
    ADD COLUMN split_policy varchar(64),
    ADD COLUMN config_json text,
    ADD COLUMN metrics_json text,
    ADD COLUMN code_version varchar(80),
    ADD COLUMN started_at timestamptz,
    ADD COLUMN finished_at timestamptz,
    ADD COLUMN error_message varchar(2000),
    ADD COLUMN claimed_by varchar(64),
    ADD COLUMN lease_expires_at timestamptz,
    ADD COLUMN reserved_model_id varchar(64),
    ADD COLUMN cancel_requested_at timestamptz;

UPDATE training_runs
SET status = 'FAILED',
    dataset_fingerprint = repeat('0', 64),
    label_schema_version = 'labels-1',
    embedding_id = 'hashing-char-ngram-v1',
    split_policy = 'split-1',
    error_message = 'PHASE 5 이전에 있던 빈 행입니다. 평가 점수는 없습니다.'
WHERE status IS NULL;

ALTER TABLE training_runs
    ALTER COLUMN status SET NOT NULL,
    ALTER COLUMN dataset_fingerprint SET NOT NULL,
    ALTER COLUMN label_schema_version SET NOT NULL,
    ALTER COLUMN embedding_id SET NOT NULL,
    ALTER COLUMN split_policy SET NOT NULL;

ALTER TABLE training_runs
    ADD CONSTRAINT training_runs_status_ck CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')
    );

CREATE UNIQUE INDEX training_runs_one_active_idx
    ON training_runs ((1))
    WHERE status IN ('QUEUED', 'RUNNING');

ALTER TABLE model_versions
    ADD COLUMN embedding_id varchar(120),
    ADD COLUMN label_schema_version varchar(64),
    ADD COLUMN dataset_fingerprint varchar(64),
    ADD COLUMN code_version varchar(80),
    ADD COLUMN device varchar(16),
    ADD COLUMN seed integer,
    ADD COLUMN config_json text,
    ADD COLUMN metrics_json text,
    ADD COLUMN model_file varchar(120),
    ADD COLUMN checksum_sha256 varchar(64),
    ADD COLUMN byte_size bigint,
    ADD COLUMN is_default boolean NOT NULL DEFAULT false;

DELETE FROM model_versions
WHERE embedding_id IS NULL;

ALTER TABLE model_versions
    ALTER COLUMN training_run_id SET NOT NULL,
    ALTER COLUMN embedding_id SET NOT NULL,
    ALTER COLUMN label_schema_version SET NOT NULL,
    ALTER COLUMN dataset_fingerprint SET NOT NULL,
    ALTER COLUMN code_version SET NOT NULL,
    ALTER COLUMN device SET NOT NULL,
    ALTER COLUMN seed SET NOT NULL,
    ALTER COLUMN config_json SET NOT NULL,
    ALTER COLUMN metrics_json SET NOT NULL,
    ALTER COLUMN model_file SET NOT NULL,
    ALTER COLUMN checksum_sha256 SET NOT NULL,
    ALTER COLUMN byte_size SET NOT NULL;

CREATE UNIQUE INDEX model_versions_one_default_idx
    ON model_versions ((1))
    WHERE is_default;

CREATE TABLE dataset_split_anchors (
    template_hash varchar(64) PRIMARY KEY,
    split varchar(16) NOT NULL,
    policy_version varchar(64) NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT dataset_split_anchors_split_ck CHECK (split IN ('TRAIN', 'VAL', 'TEST'))
);

CREATE TABLE training_examples (
    id bigserial PRIMARY KEY,
    training_run_id varchar(64) NOT NULL REFERENCES training_runs (id),
    error_case_id varchar(64) NOT NULL REFERENCES error_cases (id),
    group_key varchar(64) NOT NULL,
    split varchar(16) NOT NULL,
    label varchar(64) NOT NULL,
    template_hash varchar(64) NOT NULL,
    text_sha256 varchar(64) NOT NULL,
    CONSTRAINT training_examples_run_case_uk UNIQUE (training_run_id, error_case_id),
    CONSTRAINT training_examples_split_ck CHECK (split IN ('TRAIN', 'VAL', 'TEST'))
);

CREATE INDEX training_examples_run_idx ON training_examples (training_run_id, error_case_id);

CREATE SEQUENCE training_run_id_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE model_version_id_seq START WITH 1 INCREMENT BY 1;

COMMENT ON TABLE training_runs IS '확정 라벨 학습 실행. 조건이 부족하면 행을 만들지 않습니다.';
COMMENT ON TABLE model_versions IS '학습이 끝난 모델. is_default는 사용자가 선택할 때만 참입니다.';
