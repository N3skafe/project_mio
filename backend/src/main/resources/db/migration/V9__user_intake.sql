ALTER TABLE projects
    ALTER COLUMN default_task_id DROP NOT NULL;

ALTER TABLE error_cases
    ALTER COLUMN job_id DROP NOT NULL;

ALTER TABLE error_cases
    ADD COLUMN source_hint varchar(200);

COMMENT ON COLUMN error_cases.job_id IS '작업 실패 사례만 채웁니다. 가져온 로그는 null입니다.';
COMMENT ON COLUMN error_cases.source_hint IS '가져온 로그의 제목 또는 출처 힌트입니다. 분류 원문에는 넣지 않습니다.';
