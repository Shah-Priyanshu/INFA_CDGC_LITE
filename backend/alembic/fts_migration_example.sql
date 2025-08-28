-- Example: add FTS to asset table
-- expand
ALTER TABLE asset ADD COLUMN IF NOT EXISTS search_vector tsvector GENERATED ALWAYS AS (
  to_tsvector('simple', unaccent(coalesce(name,'') || ' ' || coalesce(description,'') || ' ' || coalesce(column_names,'')))
) STORED;
CREATE INDEX IF NOT EXISTS idx_asset_search_vector ON asset USING GIN (search_vector);

-- migrate (backfill not needed for generated column)

-- contract (example for dropping old columns/indexes if any)
-- DROP INDEX IF EXISTS idx_asset_old_search;
