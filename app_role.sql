-- Limited database role for the deployed API (data operations only: no DDL, no ownership).
-- 1. Replace CHANGE_ME with a long random password (e.g. python -c "import secrets; print(secrets.token_urlsafe(32))").
-- 2. Run with the ADMIN connection string. Do NOT commit this file with the real password in it.
-- 3. Put the resulting connection string in DATABASE_URL (Vercel + local .env).

CREATE ROLE carchive_app LOGIN PASSWORD 'epicpassword';

GRANT USAGE ON SCHEMA public TO carchive_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON cats  TO carchive_app;
GRANT SELECT, INSERT, UPDATE         ON users TO carchive_app;   -- no DELETE on users for now
-- identity columns need no separate sequence grant
