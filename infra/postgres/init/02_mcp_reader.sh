#!/bin/bash
# Read-only role for the MCP server: SELECT on marts only, no superuser, no writes.
# Runs automatically on a fresh volume (docker-entrypoint-initdb.d) and is safe to re-run.
set -euo pipefail

psql -v ON_ERROR_STOP=1 \
     --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v owner="$POSTGRES_USER" \
     -v reader="$MCP_READER_USER" \
     -v reader_password="$MCP_READER_PASSWORD" <<'SQL'
-- CREATE ROLE has no IF NOT EXISTS: build the statement only when the role is missing
SELECT format('CREATE ROLE %I LOGIN', :'reader')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'reader')
\gexec

ALTER ROLE :"reader" WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'reader_password';

-- safety defaults applied to every session of this role
ALTER ROLE :"reader" SET default_transaction_read_only = on;
ALTER ROLE :"reader" SET statement_timeout = '10s';
ALTER ROLE :"reader" SET search_path = marts;

GRANT CONNECT ON DATABASE :"DBNAME" TO :"reader";
-- PUBLIC may create temp tables by default; the reader should not write anything at all
REVOKE TEMPORARY ON DATABASE :"DBNAME" FROM PUBLIC;
GRANT USAGE ON SCHEMA marts TO :"reader";
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO :"reader";

-- dbt drops and recreates marts tables on every build; without default privileges
-- the new tables would not be readable by the reader
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA marts
    GRANT SELECT ON TABLES TO :"reader";
SQL