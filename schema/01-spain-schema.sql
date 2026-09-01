-- ============================================================================
-- matveh - schema spain: DGT vehicle registration and deregistration microdata
--
-- Run as a superuser, from the server, AFTER 00-create-database.sql:
--   sudo -u postgres psql -v ON_ERROR_STOP=1 -d matveh -f 01-spain-schema.sql
--
-- The design and the reasons are in doc/diseno-de-base-de-datos-y-etl.md, and
-- what was measured before writing this, in doc/fase0-resultados.md. What that
-- measuring changed, in one line each:
--   - the technical sheet does NOT saturate, so vehicle_spec is a deduplication
--     table with millions of rows, not a catalogue of models
--   - brand and model are dirty free text, so what groups is vehicle_type_code
--     and size_class_code, never the text
--   - codes arrive that the Anexo I does not document, so every catalogue takes
--     new codes instead of rejecting the row
--   - the monthly files carry no homologation password; only the daily ones do
--
-- Conventions kept from the model archive: no SQL keyword is used as a name,
-- jsonb would go last (there is none here), and columns are ordered widest
-- first so that alignment padding does not waste bytes on 20 million rows.
-- ============================================================================

\echo '--- this file recreates the schema; it refuses if anything is loaded'
-- The existence check and the count CANNOT be one expression: PL/pgSQL parses a
-- static query when the statement runs, so a reference to spain.registration
-- would be analysed -- and fail on a virgin database -- even when to_regclass
-- says the table is not there. Hence the nested IF and the dynamic EXECUTE,
-- which is only parsed if it is reached.
DO $guard$
DECLARE
  loaded boolean := false;
BEGIN
  IF to_regclass('spain.registration') IS NOT NULL THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM spain.registration)' INTO loaded;
  END IF;
  IF NOT loaded AND to_regclass('spain.deregistration') IS NOT NULL THEN
    EXECUTE 'SELECT EXISTS (SELECT 1 FROM spain.deregistration)' INTO loaded;
  END IF;
  IF loaded AND coalesce(current_setting('spain.allow_reset', true), '') <> 'yes' THEN
    RAISE EXCEPTION
      'spain holds loaded events and this file would delete them. If that is '
      'what you want: PGOPTIONS="-c spain.allow_reset=yes" psql -f ...';
  END IF;
END $guard$;

SET ROLE model_archive;          -- everything here belongs to the owning role

DROP TABLE IF EXISTS spain.registration, spain.deregistration, spain.staging_line,
                     spain.source_file, spain.vehicle_spec, spain.place,
                     spain.municipality, spain.province, spain.vehicle_type,
                     spain.propulsion, spain.plate_class, spain.origin,
                     spain.service, spain.procedure_type,
                     spain.deregistration_reason, spain.electric_category,
                     spain.size_class, spain.size_rule CASCADE;

BEGIN;

-- ════════════════════════════════════════════════════════════════════════════
-- 1. TWO FUNCTIONS FOR WHAT THE DGT LEAVES HALF DONE
-- ════════════════════════════════════════════════════════════════════════════

-- DDMMYYYY -> date, and NULL for anything that is not a real date. A plain
-- to_date() swallows '32012020' without complaining and invents a date out of
-- it, which is worse than a null because it looks like data.
CREATE OR REPLACE FUNCTION spain.dgt_date(txt text) RETURNS date AS $$
  SELECT CASE
    WHEN txt IS NULL OR btrim(txt) !~ '^[0-9]{8}$' THEN NULL
    WHEN substr(txt, 5, 4) < '1900' OR substr(txt, 5, 4) > '2100' THEN NULL
    ELSE to_date(txt, 'DDMMYYYY')
  END;
$$ LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE;

-- Trims, and turns into NULL the blank, the all-zeros and the '*******' that
-- KW_ITV documents as its own null. C1 control characters are dropped: seven of
-- them were measured across 1.6 million records, and they are the leftovers of
-- a CP1252 that is not declared anywhere.
CREATE OR REPLACE FUNCTION spain.dgt_text(txt text) RETURNS text AS $$
  SELECT nullif(btrim(regexp_replace(coalesce(txt, ''),
                                     E'[\u0080-\u009F]', ' ', 'g')), '');
$$ LANGUAGE sql IMMUTABLE PARALLEL SAFE;

CREATE OR REPLACE FUNCTION spain.dgt_number(txt text) RETURNS numeric AS $$
  SELECT CASE
    WHEN txt IS NULL THEN NULL
    WHEN btrim(txt) ~ '^\*+$' THEN NULL             -- KW_ITV's own null
    WHEN btrim(txt) !~ '^-?[0-9]+([.,][0-9]+)?$' THEN NULL
    ELSE replace(btrim(txt), ',', '.')::numeric
  END;
$$ LANGUAGE sql IMMUTABLE PARALLEL SAFE;

-- The DGT writes S / N / blank, and sometimes 'SI'. Anything else is NULL, not
-- false: not knowing is not the same as no.
CREATE OR REPLACE FUNCTION spain.dgt_flag(txt text) RETURNS boolean AS $$
  SELECT CASE upper(btrim(coalesce(txt, '')))
    WHEN 'S' THEN true WHEN 'SI' THEN true
    WHEN 'N' THEN false WHEN 'NO' THEN false
    ELSE NULL END;
$$ LANGUAGE sql IMMUTABLE PARALLEL SAFE;

-- ════════════════════════════════════════════════════════════════════════════
-- 2. THE CATALOGUES
--
-- Loaded from codes/*.tsv, which are extracted from doc/tablas-de-codigos.md.
-- is_documented says whether the code comes from the Anexo I or turned up in
-- the data: measured, B22 arrives in SERVICIO 2019 times, FCEV in the electric
-- category, G in propulsion, N in the procedure. A closed list would reject
-- those rows, so the load adds them here and says so.
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE spain.plate_class (
  code           text PRIMARY KEY,
  description    text NOT NULL,
  is_documented  boolean NOT NULL DEFAULT true);

CREATE TABLE spain.origin (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.service (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.propulsion (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.procedure_type (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.deregistration_reason (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.electric_category (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.vehicle_type (LIKE spain.plate_class INCLUDING ALL);
CREATE TABLE spain.province (LIKE spain.plate_class INCLUDING ALL);

-- ════════════════════════════════════════════════════════════════════════════
-- 3. THE SIZE CLASS
--
-- This is OURS, not the DGT's: the coarse classes the project needs -- small,
-- medium and large cars, off-roaders, vans, light trucks -- which no field
-- carries. The rules live in a table and not in code so that changing the
-- criterion is an UPDATE plus a reclassification, with no deployment.
--
-- THE THRESHOLDS BELOW ARE A FIRST PROPOSAL AND HAVE NOT BEEN VALIDATED BY
-- ANYONE. They are here so that there is something to argue with; they are not
-- a decision. Rules are tried in priority order and the first match wins.
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE spain.size_class (
  code           text PRIMARY KEY,
  description    text NOT NULL,
  sort_order     smallint NOT NULL DEFAULT 0);

CREATE TABLE spain.size_rule (
  rule_pk        integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  priority       smallint NOT NULL,
  size_class_code text NOT NULL REFERENCES spain.size_class,
  vehicle_type_pattern text,        -- regular expression over COD_TIPO
  min_mass_kg    integer,
  max_mass_kg    integer,
  min_wheelbase_mm integer,
  max_wheelbase_mm integer,
  note           text,
  UNIQUE (priority));

-- ════════════════════════════════════════════════════════════════════════════
-- 4. GEOGRAPHY
--
-- Two levels so the municipality name is not repeated in every combination.
-- The INE code is the key: the name is dirty text like everything else here,
-- and the first spelling seen for a code wins.
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE spain.municipality (
  municipality_pk  integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  ine_code         text NOT NULL UNIQUE,
  name             text NOT NULL,
  province_code    text REFERENCES spain.province);

CREATE TABLE spain.place (
  place_pk         integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  place_hash       text NOT NULL UNIQUE CHECK (place_hash ~ '^[0-9a-f]{64}$'),
  municipality_pk  integer REFERENCES spain.municipality,
  province_code    text REFERENCES spain.province,
  postal_code      text,
  locality         text);

-- ════════════════════════════════════════════════════════════════════════════
-- 5. THE TECHNICAL SHEET
--
-- Measured: this does NOT saturate -- some 33.000 new sheets a month -- so it
-- will hold millions of rows. It still pays for itself: each sheet is used 5.6
-- times on average and it keeps 579 bytes of text out of every event row.
--
-- Types here are the comfortable, exact ones: the byte is not paid for in a
-- table that is never scanned by the aggregates.
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE spain.vehicle_spec (
  spec_pk                integer GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  spec_hash              text NOT NULL UNIQUE CHECK (spec_hash ~ '^[0-9a-f]{64}$'),
  vehicle_type_code      text REFERENCES spain.vehicle_type,
  propulsion_code        text REFERENCES spain.propulsion,
  electric_category_code text REFERENCES spain.electric_category,
  size_class_code        text REFERENCES spain.size_class,
  brand                  text,
  model                  text,
  manufacturer           text,
  itv_type               text,
  itv_variant            text,
  itv_version            text,
  type_approval          text,
  eu_category            text,
  body_code              text,
  rd2822_class           text,
  euro_level             text,
  fuel_feed_code         text,
  base_brand             text,
  base_manufacturer      text,
  base_type              text,
  base_variant           text,
  base_version           text,
  displacement_cc        integer,
  kerb_weight_kg         integer,
  max_weight_kg          integer,
  running_mass_kg        integer,
  max_technical_mass_kg  integer,
  electric_range_km      integer,
  fiscal_power_cvf       numeric(6,2),
  power_kw               numeric(7,2),
  wheelbase_mm           smallint,
  front_track_mm         smallint,
  rear_track_mm          smallint,
  seats                  smallint,
  max_seats              smallint,
  standing_places        smallint,
  co2_g_km               smallint,
  consumption_wh_km      smallint);

CREATE INDEX vehicle_spec_type_idx  ON spain.vehicle_spec (vehicle_type_code);
CREATE INDEX vehicle_spec_size_idx  ON spain.vehicle_spec (size_class_code);
-- The password is the key to any technical catalogue, and it only arrives in
-- the daily files, so the index is partial over the rows that have one.
CREATE INDEX vehicle_spec_approval_idx ON spain.vehicle_spec (type_approval)
  WHERE type_approval IS NOT NULL;

-- ════════════════════════════════════════════════════════════════════════════
-- 6. THE LOAD CONTROL
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE spain.source_file (
  source_file_pk      bigint GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  kind                text NOT NULL CHECK (kind IN ('registration', 'deregistration')),
  granularity         text NOT NULL CHECK (granularity IN ('daily', 'monthly')),
  period              date NOT NULL,
  file_date           date,
  file_name           text NOT NULL,
  url                 text NOT NULL,
  byte_size           bigint,
  sha256              text CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  http_last_modified  timestamptz,
  http_etag           text,
  line_count          bigint,
  row_count           bigint,
  short_line_count    bigint NOT NULL DEFAULT 0,
  header_line_count   bigint NOT NULL DEFAULT 0,
  loaded_time         timestamptz NOT NULL DEFAULT now(),
  is_superseded       boolean NOT NULL DEFAULT false);

CREATE INDEX source_file_period_idx ON spain.source_file (kind, period)
  WHERE NOT is_superseded;

-- One text column, the raw line. UNLOGGED because it is rebuilt from the ZIP on
-- every load and writing its WAL would be paying twice for nothing.
CREATE UNLOGGED TABLE spain.staging_line (line text);

-- ════════════════════════════════════════════════════════════════════════════
-- 7. THE EVENTS
--
-- Partitioned by the FILE's month, not by the date of the procedure: the unit
-- of loading is the monthly file, and reloading a month has to be dropping its
-- partition. Measured: between 97.5% and 100% of the procedures of a monthly
-- file fall inside its own month, so the two are nearly the same thing anyway.
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE spain.registration (
  period                   date    NOT NULL,
  procedure_date           date    NOT NULL,
  registration_date        date,
  first_registration_date  date,
  process_date             date,
  spec_pk                  integer NOT NULL REFERENCES spain.vehicle_spec,
  place_pk                 integer REFERENCES spain.place,
  service_code             text    REFERENCES spain.service,
  plate_province_code      text    REFERENCES spain.province,
  procedure_code           text    REFERENCES spain.procedure_type,
  plate_class_code         text    REFERENCES spain.plate_class,
  origin_code              text    REFERENCES spain.origin,
  is_used                  boolean,
  is_renting               boolean,
  is_legal_person          boolean
) PARTITION BY RANGE (period);

CREATE TABLE spain.deregistration (
  period                   date    NOT NULL,
  procedure_date           date    NOT NULL,
  registration_date        date,
  first_registration_date  date,
  process_date             date,
  last_transfer_date       date,
  spec_pk                  integer NOT NULL REFERENCES spain.vehicle_spec,
  place_pk                 integer REFERENCES spain.place,
  service_code             text    REFERENCES spain.service,
  plate_province_code      text    REFERENCES spain.province,
  procedure_code           text    REFERENCES spain.procedure_type,
  reason_code              text    REFERENCES spain.deregistration_reason,
  transfer_count           smallint,
  owner_count              smallint,
  is_telematic             boolean,
  is_renting               boolean,
  is_legal_person          boolean
) PARTITION BY RANGE (period);

-- BRIN and not btree: the rows go in in date order, so the summary per block
-- range is tight, and the index costs kilobytes instead of gigabytes. Anything
-- else waits until there are real queries asking for it.
CREATE INDEX registration_procedure_date_idx   ON spain.registration   USING brin (procedure_date);
CREATE INDEX deregistration_procedure_date_idx ON spain.deregistration USING brin (procedure_date);
CREATE INDEX registration_spec_idx             ON spain.registration   (spec_pk);
CREATE INDEX deregistration_spec_idx           ON spain.deregistration (spec_pk);

-- Creates the partition of a period if it is missing, and returns its name.
-- The load calls it; nobody has to keep a list of 139 partitions up to date.
CREATE OR REPLACE FUNCTION spain.ensure_partition(which text, period date)
RETURNS text AS $$
DECLARE
  first_day date := date_trunc('month', period)::date;
  part text := format('%s_%s', which, to_char(first_day, 'YYYY_MM'));
BEGIN
  IF which NOT IN ('registration', 'deregistration') THEN
    RAISE EXCEPTION 'There is no % table', which;
  END IF;
  IF to_regclass('spain.' || part) IS NULL THEN
    EXECUTE format('CREATE TABLE spain.%I PARTITION OF spain.%I '
                   'FOR VALUES FROM (%L) TO (%L)',
                   part, which, first_day, (first_day + interval '1 month')::date);
  END IF;
  RETURN part;
END $$ LANGUAGE plpgsql SECURITY DEFINER;

-- SECURITY DEFINER so that the partition is born owned by model_archive even
-- when the load runs as archive_rw, which is the role that machines carry. The
-- two arguments are checked above, so there is nothing to inject through them.
GRANT EXECUTE ON FUNCTION spain.ensure_partition(text, date) TO archive_rw;
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

GRANT USAGE ON SCHEMA spain TO archive_ro, archive_rw;

-- ════════════════════════════════════════════════════════════════════════════
-- 8. WHAT COUNTS AS ENTERING AND LEAVING THE PARK
--
-- The convention lives here and nowhere else, so changing it is one CREATE OR
-- REPLACE VIEW and never a reload. See the design document for why each code is
-- in or out. In particular: a temporary deregistration is NOT a vehicle leaving
-- the park, and it is half of all deregistrations.
-- ════════════════════════════════════════════════════════════════════════════

CREATE OR REPLACE VIEW spain.park_entry AS
  SELECT * FROM spain.registration
   WHERE procedure_code IN ('1', '5', '8', '9');

CREATE OR REPLACE VIEW spain.park_exit AS
  SELECT * FROM spain.deregistration
   WHERE procedure_code IN ('3', '4', '7');

COMMIT;

-- ════════════════════════════════════════════════════════════════════════════
-- 9. WHAT EVERY TABLE AND EVERY DELICATE COLUMN MEANS
-- ════════════════════════════════════════════════════════════════════════════

COMMENT ON SCHEMA spain IS
  'Spain: DGT daily microdata of vehicle registrations and deregistrations, from 2014-12.';

COMMENT ON TABLE spain.registration IS
  'One row per registration procedure. CAREFUL: this is every procedure in the file, '
  'including temporary plates and their later conversion, which are the same vehicle '
  'twice. To count vehicles entering the park use the view spain.park_entry.';
COMMENT ON TABLE spain.deregistration IS
  'One row per deregistration procedure. CAREFUL: about half of these are TEMPORARY '
  'deregistrations, where the vehicle keeps existing and comes back. Counting this '
  'table as vehicles leaving the park roughly doubles the real figure: use the view '
  'spain.park_exit.';
COMMENT ON TABLE spain.vehicle_spec IS
  'The technical sheet, deduplicated by sha256 of its normalised fields. It does NOT '
  'saturate -- some 33.000 new sheets a month -- so it holds millions of rows and is '
  'not a catalogue of models. What groups is vehicle_type_code and size_class_code.';
COMMENT ON COLUMN spain.vehicle_spec.brand IS
  'MARCA_ITV, raw. DIRTY FREE TEXT: 1.491 distinct spellings in a single month, and '
  'the same car appears as VOLKSWAGEN, "VOLKSWAGEN, VW", "VOLKSWAGEN V W" and even '
  'VOLKSWAGEN BEETLE. AN AGGREGATE BY BRAND IS NOT PUBLISHABLE until this is '
  'normalised. Group by vehicle_type_code or size_class_code instead.';
COMMENT ON COLUMN spain.vehicle_spec.model IS
  'MODELO_ITV, raw, and as dirty as brand: 10.152 distinct values in one month. Same '
  'warning applies.';
COMMENT ON COLUMN spain.vehicle_spec.type_approval IS
  'CONTRASENA_HOMOLOGACION_ITV, the key to any external technical catalogue. ONLY THE '
  'DAILY FILES CARRY IT: 97.7% in the dailies against 0.0% in the monthlies, so it is '
  'null for the whole history built out of monthly files.';
COMMENT ON COLUMN spain.vehicle_spec.size_class_code IS
  'Derived by us from the rules in spain.size_rule, not a DGT field. Recomputed with '
  'an UPDATE when the criterion changes; the events never move.';
COMMENT ON TABLE spain.size_rule IS
  'The thresholds that turn masses and geometry into a coarse size class. FIRST '
  'PROPOSAL, NOT VALIDATED: they are here to be argued with. Rules apply in priority '
  'order, first match wins.';
COMMENT ON COLUMN spain.registration.period IS
  'First day of the month of the SOURCE FILE, which is what the table is partitioned '
  'by. It is not always the month of procedure_date: 0 to 2.5% of the rows carry '
  'procedures from earlier months.';
COMMENT ON COLUMN spain.registration.procedure_date IS 'FEC_TRAMITE: the date of the event itself.';
COMMENT ON COLUMN spain.registration.procedure_code IS
  'CLAVE_TRAMITE. Nullable, and it took a load to find out why: the two 707-character '
  'records of 2014-12 carry it blank. The rest of their fields are good, so they are '
  'loaded; the park_entry and park_exit views do not count them, because a null does '
  'not match an IN list -- which is the honest answer when the procedure is unknown.';
COMMENT ON COLUMN spain.registration.process_date IS
  'FEC_PROCESO: when the DGT recorded it. Null in the two records of 2014-12 that '
  'carry a ? instead of a date.';
COMMENT ON COLUMN spain.deregistration.first_registration_date IS
  'FEC_PRIM_MATRICULACION. With procedure_date it gives the AGE AT DEATH of the '
  'vehicle, which is the whole point of loading deregistrations.';
COMMENT ON COLUMN spain.deregistration.last_transfer_date IS
  'FEC_TRAMITACION, the last transfer. Empty in 96% of registrations and a date of '
  'its own in 60% of deregistrations, which is why it is only here.';
COMMENT ON COLUMN spain.deregistration.transfer_count IS
  'NUM_TRANSMISIONES: how many hands the vehicle passed through before dying.';
COMMENT ON TABLE spain.source_file IS
  'One row per file loaded. Without it there is no way to tell whether a month is in '
  'its daily version or its definitive monthly one.';
COMMENT ON TABLE spain.staging_line IS
  'Raw 714-character lines of the file being loaded. Emptied on every load.';
COMMENT ON VIEW spain.park_entry IS
  'Registrations that add a vehicle to the park: ordinary (1), re-registration (5), '
  'special vehicle (8) and temporary plate (9). The conversion from temporary to '
  'definitive (B) is left out because it is the same vehicle already counted at 9.';
COMMENT ON VIEW spain.park_exit IS
  'Deregistrations that remove a vehicle from the park: definitive (3), Plan Renove '
  '(4) and export or community transit (7). Temporary deregistration (6) is left out '
  'because the vehicle comes back.';

RESET ROLE;

\echo '--- what has been created'
\dt spain.*
\dv spain.*
