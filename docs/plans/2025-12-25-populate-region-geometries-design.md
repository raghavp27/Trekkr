# Populate Region Geometries Design

**Date**: 2025-12-25
**Status**: Approved
**Author**: Design brainstorming session

## Overview

Fill the `geom` columns in `regions_country` and `regions_state` tables with geographic boundary data from Natural Earth, while preserving all existing metadata (id, name, ISO codes).

## Goals

- Add MULTIPOLYGON geometries to existing country and state records
- Use high-quality, public domain Natural Earth 1:10m scale data
- Implement as an Alembic migration for version control and repeatability
- Match geometries to existing records by ISO codes and names
- Handle edge cases gracefully (unmatched records, invalid geometries)

## Data Sources

**Natural Earth 1:10m Scale** (high detail, suitable for mobile map zooming):

1. **Countries**: `ne_10m_admin_0_countries.shp`
   - Contains country boundaries with `iso_a2`, `iso_a3` fields
   - ~20MB compressed
   - URL: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/

2. **States/Provinces**: `ne_10m_admin_1_states_provinces.shp`
   - Contains state/province boundaries with codes and names
   - ~15MB compressed
   - URL: https://www.naturalearthdata.com/downloads/10m-cultural-vectors/

## Architecture

### Implementation Approach

**Alembic Migration** (self-contained, repeatable):
- Migration downloads shapefiles during `alembic upgrade`
- Parses with `geopandas` library
- Matches to existing DB records
- Updates `geom` columns via SQLAlchemy ORM
- Total runtime: ~5-6 minutes

### Migration Flow

```python
def upgrade():
    1. Download Natural Earth shapefiles from CDN
    2. Read shapefiles with geopandas
    3. For each country:
       - Match by ISO2/ISO3 code (case-insensitive)
       - Convert geometry to WKB format
       - UPDATE geom column
    4. For each state:
       - Match by ISO 3166-2 code or normalized name + country
       - Convert geometry to WKB format
       - UPDATE geom column
    5. Log statistics (matched, unmatched, errors)
```

## Matching Logic

### Country Matching (straightforward)

- Match Natural Earth `iso_a2`/`iso_a3` against `CountryRegion.iso2`/`iso3`
- Case-insensitive comparison
- Log warning if no match found (some Natural Earth entries may not be in our DB)

### State Matching (two-stage)

**Strategy 1 - Exact ISO Code**:
- Match Natural Earth `iso_3166_2` (e.g., "US-CA") against `StateRegion.code`
- Only if code is populated

**Strategy 2 - Fuzzy Name Matching**:
- Normalize both names: lowercase, strip whitespace, remove punctuation
- Match by normalized name + country_id
- Handles variations like "Saint" vs "St."

```python
def normalize_name(name: str) -> str:
    """Normalize for fuzzy matching."""
    return name.lower().strip().replace(".", "").replace("-", " ")
```

### Unmatched Records

- Log all unmatched records to console (informational, not error)
- Continue processing (our DB may not have every country/state)
- Report final count of unmatched records

## Geometry Handling

### Conversion Process

1. Geopandas reads shapefiles → Shapely geometry objects
2. Convert to WKB (Well-Known Binary) for PostGIS:
   ```python
   from geoalchemy2.shape import from_shape
   geom_wkb = from_shape(shapely_geometry, srid=4326)
   ```
3. Assign to SQLAlchemy model's `geom` column
4. Update `updated_at` timestamp

### Database Updates

- Use SQLAlchemy ORM (consistent with existing codebase)
- Batch commits every 50 records to reduce transaction overhead
- Update `updated_at` timestamp for each modified row
- Single transaction for entire migration (all-or-nothing)

```python
country_row = session.query(CountryRegion).filter_by(iso2=iso2).first()
if country_row:
    country_row.geom = from_shape(geometry, srid=4326)
    country_row.updated_at = datetime.utcnow()

if count % 50 == 0:
    session.commit()
```

## Error Handling

### Download Failures
- Catch network errors when fetching shapefiles
- Provide clear error message with Natural Earth URLs
- **Fail fast** - don't proceed without data

### Parse Failures
- Catch shapefile parsing errors
- Log which file failed and why
- **Fail the migration** - don't partially update

### Geometry Conversion Errors
- Some geometries may be invalid (self-intersecting, etc.)
- Log the problematic record (country/state name)
- **Skip record but continue** processing others
- Report count of skipped records at end

### Unmatched Records
- **Not an error** - just informational logging
- Our DB may intentionally not include all countries/states
- Log to console for manual review if needed

## Migration Reversibility

### Downgrade Function

```python
def downgrade():
    # Set all geom columns back to NULL
    op.execute("UPDATE regions_country SET geom = NULL")
    op.execute("UPDATE regions_state SET geom = NULL")
```

**Characteristics**:
- Destructive but reversible
- Preserves id, name, ISO code data
- Only removes geometries added by this migration
- Can re-run upgrade to restore geometries

## Dependencies

**Required additions to `requirements.txt`**:

```
geopandas>=0.14.0      # Shapefile reading & geometry handling
shapely>=2.0.0         # Geometry objects (geopandas dependency)
pyproj>=3.6.0          # Coordinate system handling (geopandas dependency)
```

**Total size**: ~50MB (industry-standard geospatial libraries)

## Performance

### Expected Runtime

- **Download**: 2-3 minutes (~30MB total)
- **Country processing**: ~10 seconds (~200 countries)
- **State processing**: 2-3 minutes (~5,000 states/provinces)
- **Total**: ~5-6 minutes

### Optimizations

- Batch commits every 50 records
- Only load necessary columns from shapefiles
- Progress logging for visibility during long operations

### Database Impact

- Adds ~50-100MB to database size (high-detail geometries)
- Enables spatial queries (ST_Contains, ST_Intersects, etc.)
- Required for PostGIS spatial indexing

## Testing

### Local Testing

```bash
# Run migration
alembic upgrade head

# Verify in psql
SELECT COUNT(*) FROM regions_country WHERE geom IS NOT NULL;
SELECT COUNT(*) FROM regions_state WHERE geom IS NOT NULL;

# Check a specific country
SELECT name, ST_AsGeoJSON(geom) FROM regions_country WHERE iso2 = 'US';
```

### Visual Verification

- Use QGIS to visualize geometries
- Or use PostGIS `ST_AsGeoJSON()` to export for web visualization
- Verify boundaries look correct for known countries

### Rollback Test

```bash
# Downgrade should set geom to NULL
alembic downgrade -1

# Verify
SELECT COUNT(*) FROM regions_country WHERE geom IS NOT NULL;  -- Should be 0
```

## Future Considerations

- **Land cells total**: Could compute `land_cells_total` by intersecting geometries with H3 grid
- **Geometry simplification**: Could add lower-resolution geometries for faster rendering at world view
- **Updates**: Natural Earth releases new versions periodically - could create new migration to refresh data
- **Other geospatial features**: Geopandas will be useful for future features (H3 cell intersection, region statistics, etc.)

## Success Criteria

- ✅ All existing records preserve their id, name, ISO codes
- ✅ Geom column populated for matched countries and states
- ✅ Migration completes in <10 minutes
- ✅ Can downgrade and re-upgrade successfully
- ✅ Unmatched records are logged but don't fail migration
- ✅ Invalid geometries are skipped with warnings

## Resources

- [Natural Earth Data](https://www.naturalearthdata.com/)
- [Geopandas Documentation](https://geopandas.org/)
- [GeoAlchemy2 Documentation](https://geoalchemy-2.readthedocs.io/)
- [PostGIS Reference](https://postgis.net/docs/)
