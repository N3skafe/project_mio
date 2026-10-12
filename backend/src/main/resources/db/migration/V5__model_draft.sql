ALTER TABLE error_cases
    ADD COLUMN inference_state varchar(16) NOT NULL DEFAULT 'READY',
    ADD COLUMN model_version_id varchar(64);

ALTER TABLE error_cases
    ALTER COLUMN draft_label DROP NOT NULL,
    ALTER COLUMN current_label DROP NOT NULL;

ALTER TABLE error_cases
    ADD CONSTRAINT error_cases_inference_ck CHECK (inference_state IN ('PENDING', 'READY')),
    ADD CONSTRAINT error_cases_pending_label_ck CHECK (
        (inference_state = 'PENDING' AND draft_label IS NULL AND current_label IS NULL AND draft_source = 'MODEL')
        OR (inference_state = 'READY' AND draft_label IS NOT NULL AND current_label IS NOT NULL)
    );

CREATE TABLE draft_inferences (
    id varchar(64) PRIMARY KEY,
    error_case_id varchar(64) NOT NULL UNIQUE REFERENCES error_cases (id),
    model_version_id varchar(64) NOT NULL REFERENCES model_versions (id),
    status varchar(16) NOT NULL,
    claimed_by varchar(64),
    lease_expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    finished_at timestamptz,
    CONSTRAINT draft_inferences_status_ck CHECK (status IN ('QUEUED', 'RUNNING', 'DONE', 'FAILED'))
);

CREATE INDEX draft_inferences_status_idx ON draft_inferences (status, created_at);

CREATE SEQUENCE draft_inference_id_seq START WITH 1 INCREMENT BY 1;

COMMENT ON TABLE draft_inferences IS '기본 모델의 실패 로그 초안. 응답이 없으면 규칙 초안으로 닫고 다시 넣지 않습니다.';
