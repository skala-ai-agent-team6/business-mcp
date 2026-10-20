-- Add fields needed by get_part_availability to an existing business-mcp database.
BEGIN;

ALTER TABLE warehouse ADD COLUMN IF NOT EXISTS location text;
ALTER TABLE factory ADD COLUMN IF NOT EXISTS contact_name text;
ALTER TABLE factory ADD COLUMN IF NOT EXISTS email text;
ALTER TABLE part_supplier
    ADD COLUMN IF NOT EXISTS unit_price numeric(12,2) CHECK (unit_price >= 0);

COMMIT;
