-- Grants the loading role the two things it was missing, on a schema that
-- already exists:
--
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -d matveh -f 2026-09-01-loader-grants.sql
--
-- Same content as in 01-spain-schema.sql. Found by running the load as
-- archive_rw, which is how it is supposed to run: an ETL needs no ownership.

-- What the loading role needs beyond the default privileges, and nothing more:
--
--   TRUNCATE on the staging table only. It exists to be emptied on every load,
--   and TRUNCATE otherwise belongs to the owner. Granting it on the event tables
--   instead would hand over the power to wipe eleven years in one statement.
--
--   TEMPORARY on the database, because the load slices the raw line into a
--   temporary table. PUBLIC has it by default; it is stated here so that the day
--   someone revokes PUBLIC, the load does not stop with a puzzling error.
-- No pager, ever: psql pipes its output through less when it is writing to a
-- terminal, and then it waits for a keypress. A script that stops to be read is
-- not automatable.
\pset pager off

GRANT TRUNCATE ON spain.staging_line TO archive_rw;
GRANT TEMPORARY ON DATABASE matveh TO archive_rw;
