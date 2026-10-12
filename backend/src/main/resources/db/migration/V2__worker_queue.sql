ALTER TABLE jobs ADD COLUMN worker_id varchar(64);
ALTER TABLE jobs ADD COLUMN lease_expires_at timestamptz;
ALTER TABLE jobs ADD COLUMN exit_code integer;
ALTER TABLE jobs ADD COLUMN cancel_confirmed_at timestamptz;

ALTER TABLE job_events ADD COLUMN stream varchar(16) NOT NULL DEFAULT 'SYSTEM';
ALTER TABLE job_events ADD CONSTRAINT job_events_stream_ck CHECK (stream IN ('STDOUT', 'STDERR', 'SYSTEM'));

ALTER TABLE registered_tasks ADD COLUMN argv_json varchar(2000);
ALTER TABLE registered_tasks ADD COLUMN relative_workdir varchar(200);
ALTER TABLE registered_tasks ADD COLUMN timeout_seconds integer;

CREATE TABLE worker_sessions (
    worker_id varchar(64) PRIMARY KEY,
    last_heartbeat_at timestamptz NOT NULL
);

INSERT INTO projects (id, name, summary, default_task_id) VALUES
    (
        'trusted-sample',
        '신뢰 샘플',
        '로컬 fixture만 실행하는 등록 프로젝트입니다. 사용자 입력은 명령이 되지 않습니다.',
        'api-db-check'
    );

INSERT INTO registered_tasks (id, project_id, name, plan_text, argv_json, relative_workdir, timeout_seconds) VALUES
    (
        'sample-pass',
        'trusted-sample',
        '성공 픽스처',
        '서버에 등록된 argv만 실행합니다. 토큰 {python}은 워커의 인터프리터입니다. 셸 문자열이 아닙니다.',
        '["{python}","pass_check.py"]',
        'sample',
        10
    ),
    (
        'sample-fail',
        'trusted-sample',
        '실패 픽스처',
        '종료 코드 2와 stderr를 남기는 등록 명령입니다. 사용자 입력을 실행하지 않습니다.',
        '["{python}","fail_check.py"]',
        'sample',
        10
    ),
    (
        'sample-slow',
        'trusted-sample',
        '지연 픽스처',
        '취소와 타임아웃을 재현하는 등록 명령입니다. 오래 잠들었다가 출력합니다.',
        '["{python}","slow_check.py"]',
        'sample',
        30
    );

UPDATE projects SET default_task_id = 'sample-pass' WHERE id = 'trusted-sample';
