-- Adds spain.reset_partition to a schema that already exists, so that the load
-- can replace a month without owning the tables.
--
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -d matveh -f 2026-09-01-reset-partition.sql
--
-- Same content as the function in 01-spain-schema.sql. Changing one function
-- does not need the whole schema rerun, and rerunning it would delete the data.
-- No pager, ever: psql pipes its output through less when it is writing to a
-- terminal, and then it waits for a keypress. A script that stops to be read is
-- not automatable.
\pset pager off

SET ROLE model_archive;

-- Empties a period and leaves its partition ready: what a monthly load needs,
-- since the monthly file replaces whatever the period held.
--
-- SECURITY DEFINER for the same reason as ensure_partition: dropping a partition
-- belongs to the owner, and the loading role has no business owning tables. The
-- alternative was granting TRUNCATE on every partition to archive_rw, which
-- gives away more than the load needs.
CREATE OR REPLACE FUNCTION spain.reset_partition(which text, period date)
RETURNS text AS $$
DECLARE
  first_day date := date_trunc('month', period)::date;
  part text := format('%s_%s', which, to_char(first_day, 'YYYY_MM'));
BEGIN
  IF which NOT IN ('registration', 'deregistration') THEN
    RAISE EXCEPTION 'There is no % table', which;
  END IF;
  EXECUTE format('DROP TABLE IF EXISTS spain.%I', part);
  RETURN spain.ensure_partition(which, first_day);
END $$ LANGUAGE plpgsql SECURITY DEFINER;

GRANT EXECUTE ON FUNCTION spain.reset_partition(text, date) TO archive_rw;

RESET ROLE;
