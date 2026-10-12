CREATE TABLE projects (
    id varchar(64) PRIMARY KEY,
    name varchar(120) NOT NULL,
    summary varchar(500) NOT NULL,
    default_task_id varchar(64) NOT NULL
);

CREATE TABLE registered_tasks (
    id varchar(64) PRIMARY KEY,
    project_id varchar(64) NOT NULL REFERENCES projects (id),
    name varchar(120) NOT NULL,
    plan_text varchar(1000) NOT NULL
);

INSERT INTO projects (id, name, summary, default_task_id) VALUES
    ('demo-api', '데모 API', 'LIVE 등록 프로젝트입니다. 실행 워커는 연결되지 않습니다.', 'api-db-check'),
    ('demo-web', '데모 Web', 'LIVE 등록 프로젝트입니다. 실행 워커는 연결되지 않습니다.', 'web-health');

INSERT INTO registered_tasks (id, project_id, name, plan_text) VALUES
    (
        'api-db-check',
        'demo-api',
        'DB 연결 점검 자리',
        '등록된 작업 api-db-check 입니다. 이 단계는 계획을 셸로 실행하지 않습니다. 작업을 만들면 QUEUED로 저장되고, 워커가 없으므로 성공이나 실패로 바뀌지 않습니다.'
    ),
    (
        'web-health',
        'demo-web',
        '상태 점검 자리',
        '등록된 작업 web-health 입니다. 이 단계는 계획을 셸로 실행하지 않습니다. 작업을 만들면 QUEUED로 저장되고, 워커가 없으므로 성공이나 실패로 바뀌지 않습니다.'
    );

ALTER TABLE projects
    ADD CONSTRAINT projects_default_task_fk
    FOREIGN KEY (default_task_id) REFERENCES registered_tasks (id);

CREATE SEQUENCE job_id_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE error_case_id_seq START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE resolution_id_seq START WITH 1 INCREMENT BY 1;

CREATE TABLE jobs (
    id varchar(64) PRIMARY KEY,
    project_id varchar(64) NOT NULL REFERENCES projects (id),
    task_id varchar(64) NOT NULL REFERENCES registered_tasks (id),
    status varchar(32) NOT NULL,
    created_at timestamptz NOT NULL,
    started_at timestamptz,
    finished_at timestamptz,
    cancel_requested_at timestamptz,
    output_truncated boolean NOT NULL DEFAULT false,
    CONSTRAINT jobs_status_ck CHECK (
        status IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCEL_REQUESTED', 'CANCELLED')
    )
);

CREATE INDEX jobs_created_at_id_idx ON jobs (created_at, id);

CREATE TABLE job_events (
    id bigserial PRIMARY KEY,
    job_id varchar(64) NOT NULL REFERENCES jobs (id),
    sequence_no integer NOT NULL,
    text varchar(2000) NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT job_events_job_sequence_uk UNIQUE (job_id, sequence_no)
);

CREATE INDEX job_events_job_sequence_idx ON job_events (job_id, sequence_no);

CREATE TABLE idempotency_keys (
    key_text varchar(128) PRIMARY KEY,
    request_hash varchar(64) NOT NULL,
    job_id varchar(64) REFERENCES jobs (id),
    created_at timestamptz NOT NULL
);

CREATE TABLE error_cases (
    id varchar(64) PRIMARY KEY,
    job_id varchar(64) NOT NULL REFERENCES jobs (id),
    project_id varchar(64) NOT NULL REFERENCES projects (id),
    raw_text varchar(8000) NOT NULL,
    draft_label varchar(64) NOT NULL,
    draft_source varchar(32) NOT NULL,
    current_label varchar(64) NOT NULL,
    review_status varchar(32) NOT NULL,
    origin varchar(32) NOT NULL,
    created_at timestamptz NOT NULL,
    CONSTRAINT error_cases_label_ck CHECK (
        draft_label IN ('DB_CONNECTION', 'AUTH_PERMISSION', 'EXTERNAL_NETWORK', 'INPUT_VALIDATION', 'OTHER')
        AND current_label IN ('DB_CONNECTION', 'AUTH_PERMISSION', 'EXTERNAL_NETWORK', 'INPUT_VALIDATION', 'OTHER')
    ),
    CONSTRAINT error_cases_status_ck CHECK (
        review_status IN ('DRAFT', 'APPROVED', 'REVISED', 'DEFERRED')
    )
);

CREATE INDEX error_cases_created_at_id_idx ON error_cases (created_at, id);

CREATE TABLE label_revisions (
    id bigserial PRIMARY KEY,
    error_case_id varchar(64) NOT NULL REFERENCES error_cases (id),
    label varchar(64) NOT NULL,
    review_status varchar(32) NOT NULL,
    source varchar(32) NOT NULL,
    note varchar(1000) NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX label_revisions_case_idx ON label_revisions (error_case_id, created_at);

CREATE TABLE resolution_records (
    id varchar(64) PRIMARY KEY,
    error_case_id varchar(64) NOT NULL REFERENCES error_cases (id),
    project_id varchar(64) NOT NULL REFERENCES projects (id),
    label varchar(64) NOT NULL,
    cause varchar(500) NOT NULL,
    method varchar(500) NOT NULL,
    origin varchar(32) NOT NULL,
    created_at timestamptz NOT NULL
);

CREATE INDEX resolution_records_created_at_id_idx ON resolution_records (created_at, id);

CREATE TABLE training_runs (
    id varchar(64) PRIMARY KEY,
    created_at timestamptz NOT NULL
);

CREATE TABLE model_versions (
    id varchar(64) PRIMARY KEY,
    training_run_id varchar(64) REFERENCES training_runs (id),
    created_at timestamptz NOT NULL
);

COMMENT ON TABLE training_runs IS 'PHASE 5까지 비어 있습니다. 점수를 넣지 않습니다.';
COMMENT ON TABLE model_versions IS 'PHASE 5까지 비어 있습니다. 점수를 넣지 않습니다.';
