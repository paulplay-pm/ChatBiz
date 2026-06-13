-- =============================================================================
-- 02-create-databases.sql (TEST VARIANT)
--
-- Test-stack specific override of the production 02-create-databases.sql.
-- Postgres 16 disallows CREATE DATABASE inside a function/DO block, so we
-- use psql meta-commands with IF NOT EXISTS guards via \gexec.
--
-- The production init script (infrastructure/postgres/init/02-create-databases.sql)
-- uses a DO block that fails on Postgres 16. The test stack uses THIS file
-- (infrastructure/postgres-init-test/02-create-databases.sql) as a workaround
-- so the test stack can boot.
--
-- The production script needs a separate fix tracked outside this change.
-- =============================================================================

SELECT 'CREATE DATABASE audit_isolation'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'audit_isolation')\gexec

SELECT 'CREATE DATABASE workflow_engine'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'workflow_engine')\gexec

\connect audit_isolation
GRANT ALL PRIVILEGES ON DATABASE audit_isolation TO chatbiz;
GRANT ALL ON SCHEMA public TO chatbiz;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chatbiz;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chatbiz;

\connect workflow_engine
GRANT ALL PRIVILEGES ON DATABASE workflow_engine TO chatbiz;
GRANT ALL ON SCHEMA public TO chatbiz;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chatbiz;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chatbiz;
