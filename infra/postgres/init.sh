#!/bin/sh
set -eu
export APP_DB_PASSWORD="$(cat /run/secrets/db_password)"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\getenv app_password APP_DB_PASSWORD
CREATE ROLE atlas LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CONNECT ON DATABASE atlasops TO atlas;
GRANT USAGE, CREATE ON SCHEMA public TO atlas;
SQL
unset APP_DB_PASSWORD
