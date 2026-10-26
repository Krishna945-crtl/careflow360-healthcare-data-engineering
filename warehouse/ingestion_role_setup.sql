-- Run as an account administrator, selecting each statement or running the entire script.
-- Existing CAREFLOW_DB and its RAW tables must already exist.
-- Replace <YOUR_USER> in the final statement with the quoted username shown by SELECT CURRENT_USER().
CREATE ROLE IF NOT EXISTS CAREFLOW_INGEST_ROLE;
GRANT USAGE ON WAREHOUSE CAREFLOW_WH TO ROLE CAREFLOW_INGEST_ROLE;
GRANT USAGE ON DATABASE CAREFLOW_DB TO ROLE CAREFLOW_INGEST_ROLE;
GRANT USAGE ON SCHEMA CAREFLOW_DB.RAW TO ROLE CAREFLOW_INGEST_ROLE;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA CAREFLOW_DB.RAW TO ROLE CAREFLOW_INGEST_ROLE;
-- Check which Snowflake login you are using:
SELECT CURRENT_USER();
-- Run separately, with your actual username (never literal placeholder):
-- GRANT ROLE CAREFLOW_INGEST_ROLE TO USER "<YOUR_USER>";
