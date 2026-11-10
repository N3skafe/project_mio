CREATE TABLE trainer_sessions (
    trainer_id varchar(64) PRIMARY KEY,
    last_heartbeat_at timestamptz NOT NULL
);
