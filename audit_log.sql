-- Audit log (run once with the ADMIN connection string, in the Neon SQL editor with "Run").
-- Safe to re-run. The app role gets INSERT and SELECT only: it can add entries but can never
-- change or delete them, so the log can't be rewritten through the API or a stolen app password.

CREATE TABLE IF NOT EXISTS audit_log (
    id             BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    action         VARCHAR(40) NOT NULL,                 -- user.register | cat.create | cat.update | cat.moderate | cat.delete
    actor_id       INTEGER REFERENCES users (id) ON DELETE SET NULL,
    actor_username VARCHAR(30),                          -- copied, so it survives the account being removed
    actor_role     VARCHAR(10),
    target_type    VARCHAR(20) NOT NULL,                 -- cat | user
    target_id      INTEGER,
    details        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- what changed (old -> new), never secrets
    ip_address     VARCHAR(64),
    request_id     VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS audit_log_occurred_idx ON audit_log (occurred_at DESC);
CREATE INDEX IF NOT EXISTS audit_log_actor_idx    ON audit_log (actor_id);
CREATE INDEX IF NOT EXISTS audit_log_target_idx   ON audit_log (target_type, target_id);

GRANT SELECT, INSERT ON audit_log TO carchive_app;
