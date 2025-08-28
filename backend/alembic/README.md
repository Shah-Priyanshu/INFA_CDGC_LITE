Alembic migrations live here.

FTS pattern:
- Add generated column `search_vector` with unaccent on name/description/column_names
- Create GIN index on `search_vector`
- Use `plainto_tsquery('simple', unaccent(:q))` and `ts_headline` for highlighting in queries
