-- =============================================================================
-- 01-credential-schema.sql
--
-- Bootstrap SQL executed by the official postgres image's
-- docker-entrypoint-initdb.d hook on FIRST container start (i.e. when the
-- data directory is empty). The credential service then takes over schema
-- management via Alembic (alembic/versions/0001_initial.py, Task 2).
--
-- This file exists so that:
--   1. The `credential` database is guaranteed to exist before Alembic runs.
--   2. We have a single place to grant privileges to the `chatbiz` role.
--   3. We can create the `pgcrypto` extension for gen_random_uuid().
--
-- We intentionally do NOT define application tables here; Alembic is the
-- source of truth for the schema.
-- =============================================================================

-- Required for gen_random_uuid() (used by the encryption_keys table in
-- the initial Alembic migration).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- The postgres image's POSTGRES_USER / POSTGRES_DB env already creates the
-- `chatbiz` role and the `credential` database. We just make sure the role
-- has full privileges on the database (default in the image, but be
-- explicit in case the role was overridden).
GRANT ALL PRIVILEGES ON DATABASE credential TO chatbiz;
GRANT ALL ON SCHEMA public TO chatbiz;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO chatbiz;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO chatbiz;
