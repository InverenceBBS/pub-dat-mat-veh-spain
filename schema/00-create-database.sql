-- ============================================================================
-- matveh - database, spain schema and privileges
--
-- Run ONCE per server, as a superuser, FROM the server itself:
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -f /home/devel/00-create-database.sql
--
-- ROLES ARE NOT CREATED HERE. matveh reuses the three roles of the model
-- archive, so no new password is issued and the credential files already in
-- place (~/.pgpass, /etc/inverence/archive.env) keep working: only PGDATABASE
-- changes.
--   model_archive  owns the database and the schema; DDL only, from the server
--   archive_ro     reads
--   archive_rw     reads, inserts, updates, deletes
--
-- ONE SCHEMA PER COUNTRY. spain holds the DGT microdata; another country gets
-- another schema in this same database, so nothing ever lands in public.
--
-- The whole file is idempotent, CREATE DATABASE included: it is skipped when
-- matveh is already there, and everything after it is stated rather than
-- created, so running this on a database that already holds tables adjusts the
-- privileges and touches no data.
--
-- ENCODING is the one thing that cannot be fixed afterwards: a pre-existing
-- database with the wrong one has to be dumped, dropped and recreated. The
-- check below says so instead of carrying on quietly.
--
-- NOT DONE HERE, because it lives outside the cluster: pg_hba.conf matches by
-- database name, so if its rules name model_archive explicitly, matveh stays
-- unreachable until a line is added -- and that line also picks the auth
-- method (see docs: the archive is on md5 as a workaround for the libpq 9.5 of
-- the TOL container, a debt matveh need not inherit).
-- ============================================================================

\echo '--- the three roles must already exist'
DO $guard$
DECLARE
  missing text;
BEGIN
  SELECT string_agg(r, ', ')
    INTO missing
    FROM unnest(ARRAY['model_archive', 'archive_ro', 'archive_rw']) AS r
   WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r);
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'Missing role(s): %. matveh reuses the model archive roles and creates none.', missing;
  END IF;
END $guard$;

\echo '--- database (created only if missing)'
SELECT 'CREATE DATABASE matveh OWNER model_archive ENCODING ''UTF8'' TEMPLATE template0'
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'matveh')
\gexec

-- Stated, not assumed: an already existing matveh may have been created by
-- another hand and owned by whoever ran it.
ALTER DATABASE matveh OWNER TO model_archive;

DO $enc$
DECLARE
  enc text;
BEGIN
  SELECT pg_encoding_to_char(encoding) INTO enc FROM pg_database WHERE datname = 'matveh';
  IF enc <> 'UTF8' THEN
    RAISE EXCEPTION 'matveh already exists with encoding % and it cannot be changed in place: dump it, drop it and run this file again.', enc;
  END IF;
END $enc$;

COMMENT ON DATABASE matveh IS
  'Vehicle registration and deregistration microdata. One schema per country.';

-- Explicit access only: no role connects because it happens to be logged in.
REVOKE CONNECT ON DATABASE matveh FROM PUBLIC;
GRANT  CONNECT ON DATABASE matveh TO archive_ro, archive_rw;

\connect matveh

\echo '--- schema'
CREATE SCHEMA IF NOT EXISTS spain AUTHORIZATION model_archive;

COMMENT ON SCHEMA spain IS
  'Spain: DGT daily microdata of vehicle registrations and deregistrations.';

-- Nothing is meant to be created in public.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

GRANT USAGE ON SCHEMA spain TO archive_ro, archive_rw;

-- A session lands in spain without qualifying every table.
ALTER DATABASE matveh SET search_path = spain, public;

-- Set per database, NOT left to the client. A Windows client negotiates
-- client_encoding from its locale and writes mojibake: the model archive has a
-- 'PredicciÃ³n (forecast)' published from a Windows box. The source files are
-- ISO-8859-1, so they are transcoded on load and everything in here is UTF-8.
ALTER DATABASE matveh SET client_encoding TO 'UTF8';

-- Every instant is UTC. A ::timestamptz cast reads a zoneless text in the
-- SESSION time zone, so the same file loaded from two machines would store two
-- different instants; this makes the default the same everywhere.
ALTER DATABASE matveh SET timezone TO 'UTC';

\echo '--- privileges on what exists (nothing yet) and on what will exist'
GRANT SELECT                         ON ALL TABLES    IN SCHEMA spain TO archive_ro;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA spain TO archive_rw;
GRANT USAGE                          ON ALL SEQUENCES IN SCHEMA spain TO archive_rw;

-- Tables are created by the owning role, so the defaults are set FOR that role:
-- privileges granted to a different creator would not apply.
ALTER DEFAULT PRIVILEGES FOR ROLE model_archive IN SCHEMA spain
  GRANT SELECT                         ON TABLES    TO archive_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE model_archive IN SCHEMA spain
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES    TO archive_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE model_archive IN SCHEMA spain
  GRANT USAGE                          ON SEQUENCES TO archive_rw;

\echo '--- check: owner, encoding, schemas, what is already stored'
\l matveh
\dn+
\ddp
SELECT n.nspname AS schema, count(c.oid) AS tables
  FROM pg_namespace n
  LEFT JOIN pg_class c ON c.relnamespace = n.oid AND c.relkind IN ('r', 'p')
 WHERE n.nspname NOT IN ('pg_catalog', 'pg_toast', 'information_schema')
 GROUP BY 1 ORDER BY 1;
SELECT unnest(setconfig) AS database_setting
  FROM pg_db_role_setting s JOIN pg_database d ON d.oid = s.setdatabase
 WHERE d.datname = 'matveh' AND s.setrole = 0;
