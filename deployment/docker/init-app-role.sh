#!/bin/sh
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password DIVAN_DB_PASSWORD
CREATE ROLE divannameh LOGIN PASSWORD :'app_password';
ALTER DATABASE divannameh OWNER TO divannameh;
SQL
