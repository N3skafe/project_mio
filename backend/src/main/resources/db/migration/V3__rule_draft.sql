ALTER TABLE error_cases
    ADD COLUMN rule_version varchar(64),
    ADD COLUMN matched_keyword varchar(120);
