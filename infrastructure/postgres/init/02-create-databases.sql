-- =============================================================================
-- 02-create-databases.sql
--
-- Create the per-service databases that are NOT the default POSTGRES_DB
-- (which is `credential` per the compose env). This file runs once on
-- first container start alongside 01-credential-schema.sql.
--
-- The service-migrate containers for audit-and-isolation and
-- workflow-engine both call `alembic upgrade head` against their own
-- database URL (postgresql+asyncpg://chatbiz:chatbiz@postgres:5432/
-- audit_isolation or /workflow_engine). Postgres refuses connections to
-- non-existent databases, so we must CREATE them here before the
-- `depends_on: service_healthy` chain lets those migrate containers run.
--
-- Note: we use a DO block guarded by `SELECT 1 FROM pg_database` so
-- re-running this script (e.g. after a manual `psql -f`) is idempotent.
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'audit_isolation') THEN
        EXECUTE 'CREATE DATABASE audit_isolation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'workflow_engine') THEN
        EXECUTE 'CREATE DATABASE workflow_engine';
    END IF;
END
$$;

-- Grant chatbiz role full privileges on the new databases. The DO block
-- above created them as the postgres superuser, so we need to assign
-- ownership to the chatbiz role explicitly.
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
