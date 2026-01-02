# Batch Location Ingestion Design

## Overview

This document describes the design for batch location ingestion in Trekkr, enabling efficient sync of multiple locations collected offline or batched in the background.

## Problem Statement

The current single-location ingestion endpoint (`POST /location/ingest`) processes one location at a time. This is inefficient for:

1. **Offline sync**: Users explore for hours/days without connectivity, then need to sync hundreds of queued locations
2. **Background batching**: App collects locations in real-time but wants to reduce API calls by batching every 5-10 minutes

Sending locations one-by-one causes:
- High API call count (10-50x more requests)
- Increased network usage and battery drain on mobile
- Higher server load from connection overhead

## Design Decisions

### 1. Use Case: Both Offline Sync and Background Batching
The design handles both scenarios:
- Long gaps in timestamps (offline)
- Tight timestamp clusters (real-time batching)
- Mixed stale and fresh data

### 2. Error Handling: Partial Success
Invalid locations are skipped with reasons; valid locations are always processed.

**Rationale**: During offline sync, we don't want to lose hours of valid location data because one GPS reading was corrupted.

### 3. Deduplication: First Occurrence Wins
If the same H3 cell appears multiple times in a batch, use the first (earliest) timestamp.

**Rationale**: For discovery tracking, the first time you entered a cell is what matters. Subsequent visits in the same batch are noise (likely GPS pings while stationary).

### 4. Reverse Geocoding: Group by Res-6 Parent
Dedupe to unique res-6 cells first, geocode once per res-6 cell, apply result to all child res-8 cells.

**Rationale**: Res-6 cells are ~36km² - the chance of spanning country/state borders is very low, and query reduction is significant (5-20x typically).

### 5. Discovery Detection: Pre-Query + In-Batch Tracking
Before processing, query which countries/states user has visited. Track discoveries as we process.

**Rationale**: Users want immediate feedback on discoveries ("You just discovered Japan!"), and pre-querying is a single indexed query.

### 6. Response Format: Aggregated Summary
Return counts and lists of new countries/states, but NOT every individual cell.

**Rationale**: The client already knows which cells it sent. It mainly needs discoveries, achievement unlocks, and processing stats.

### 7. Batch Size: 100 Locations Max, Client-Side Chunking
For >100 locations, client splits into batches and sends sequentially.

**Rationale**:
- Resilience: If batch 3 of 5 fails, client only retries batch 3
- Progress feedback: Client can show "Syncing... 200/500 locations"
- Memory efficiency: Server never holds more than 100 locations in memory
- Simplicity: No server-side cursor/continuation state

### 8. Rate Limit: 30 Requests/Minute
With 100 locations per batch, this allows 3,000 locations/minute max.

**Rationale**: 3,000 locations/minute is ~10 hours of continuous tracking at 5-second intervals. More than enough headroom while preventing abuse.

---

## API Contract

### Endpoint

```
POST /api/v1/location/ingest/batch
```

**Rate Limit**: 30 requests/minute per user

### Request Schema

```json
{
  "locations": [
    {
      "latitude": 37.7749,
      "longitude": -122.4194,
      "h3_res8": "882830810ffffff",
      "timestamp": "2024-12-28T10:30:00Z"
    },
    {
      "latitude": 37.7850,
      "longitude": -122.4094,
      "h3_res8": "882830811ffffff",
      "timestamp": "2024-12-28T10:35:00Z"
    }
  ],
  "device_uuid": "optional-uuid",
  "device_name": "iPhone 15",
  "platform": "ios"
}
```

**Constraints**:
- 1-100 locations per batch (validated at schema level)
- Each location requires: `latitude`, `longitude`, `h3_res8`
- `timestamp` is optional (defaults to now, but strongly recommended for offline sync)
- Device metadata at batch level (not per-location) to reduce payload size

### Response Schema

```json
{
  "processed": 95,
  "skipped": 5,
  "skipped_reasons": [
    {"index": 12, "reason": "h3_mismatch"},
    {"index": 45, "reason": "invalid_coordinates"}
  ],
  "discoveries": {
    "new_countries": [{"id": 1, "name": "Japan", "iso2": "JP"}],
    "new_regions": [{"id": 42, "name": "Tokyo", "code": "13"}],
    "new_cells_res6": 8,
    "new_cells_res8": 42
  },
  "achievements_unlocked": [
    {"code": "explorer", "name": "Explorer", "description": "Visit 100 unique cells"}
  ]
}
```

### Error Responses

| Status | Condition |
|--------|-----------|
| 400 | All locations invalid (nothing to process) |
| 401 | Missing or invalid authentication token |
| 422 | Empty locations array or >100 locations |
| 429 | Rate limit exceeded (>30 requests/minute) |
| 503 | Database error during processing |

---

## Processing Algorithm

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. VALIDATE & DEDUPLICATE                                       │
│    • Validate each location (coords, H3 format, H3 matches GPS) │
│    • Track invalid locations with reasons (don't fail batch)    │
│    • Dedupe by H3 res-8: keep first occurrence per cell         │
│    • Result: list of valid, unique locations                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. PRE-QUERY USER'S EXISTING VISITS                             │
│    • Get set of countries user has already visited              │
│    • Get set of states/regions user has already visited         │
│    • Get set of H3 cells user has already visited (res 6 & 8)   │
│    • These sets enable discovery detection during processing    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. GROUP BY RES-6 PARENT & REVERSE GEOCODE                      │
│    • Derive res-6 parent for each res-8 cell                    │
│    • Group locations by unique res-6 cell                       │
│    • Reverse geocode once per unique res-6 (PostGIS query)      │
│    • Apply country_id/state_id to all child res-8 cells         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. BULK UPSERT CELLS & VISITS                                   │
│    • Bulk upsert h3_cells (global registry) via UNNEST          │
│    • Bulk upsert user_cell_visits via UNNEST                    │
│    • Track which cells/countries/states are newly discovered    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. CHECK ACHIEVEMENTS (once at end)                             │
│    • Call AchievementService.check_and_unlock()                 │
│    • Only one achievement check per batch (not per cell)        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 6. BUILD RESPONSE                                               │
│    • Aggregate: processed count, skipped count with reasons     │
│    • List new countries/regions discovered                      │
│    • Count new cells (res-6 and res-8)                          │
│    • List achievements unlocked                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Key Optimizations vs. Single-Location Flow

| Aspect | Single Location | Batch (100 locations) |
|--------|-----------------|----------------------|
| Reverse geocode calls | 1 per request | 1 per unique res-6 cell (~5-20) |
| SQL inserts | 4 per request | 2 bulk operations total |
| Achievement checks | 1 per request | 1 per batch |
| DB round-trips | ~6 per request | ~5 per batch |

---

## Data Flow

### Validation Rules

Each location is validated independently:

1. **Latitude**: Must be between -90 and 90
2. **Longitude**: Must be between -180 and 180
3. **H3 Index**: Must be valid H3 cell at resolution 8
4. **H3 Match**: H3 index must match coordinates (with 1-ring neighbor tolerance for GPS jitter)

### Deduplication Logic

```python
seen_cells = set()
valid_locations = []

for location in locations:
    if location.h3_res8 in seen_cells:
        continue  # Skip duplicate, keep first occurrence
    seen_cells.add(location.h3_res8)
    valid_locations.append(location)
```

### Discovery Detection

```python
# Pre-query existing visits
existing = {
    'country_ids': {1, 2, 5},      # Countries user has visited
    'state_ids': {10, 15, 22},     # States user has visited
    'h3_res6': {'861...', ...},    # Res-6 cells user has visited
    'h3_res8': {'881...', ...},    # Res-8 cells user has visited
}

# During processing, track new discoveries
new_countries = []
new_states = []

for cell in processed_cells:
    if cell.country_id not in existing['country_ids']:
        new_countries.append(cell.country)
        existing['country_ids'].add(cell.country_id)  # Don't rediscover in same batch
```

---

## Client Integration Guide

### Chunking Large Syncs

```typescript
const BATCH_SIZE = 100;

async function syncLocations(locations: Location[]): Promise<SyncResult> {
  const batches = chunk(locations, BATCH_SIZE);
  const results: BatchResponse[] = [];

  for (let i = 0; i < batches.length; i++) {
    try {
      const response = await api.post('/location/ingest/batch', {
        locations: batches[i],
        device_uuid: deviceId,
        platform: 'ios'
      });
      results.push(response);

      // Update progress UI
      onProgress((i + 1) / batches.length);
    } catch (error) {
      if (error.status === 429) {
        // Rate limited - wait and retry
        await sleep(60000);
        i--;  // Retry this batch
      } else {
        throw error;
      }
    }
  }

  return aggregateResults(results);
}
```

### Handling Partial Success

```typescript
const response = await api.post('/location/ingest/batch', { locations });

if (response.skipped > 0) {
  // Log skipped locations for debugging
  console.warn('Some locations skipped:', response.skipped_reasons);

  // Optionally notify user
  if (response.skipped > response.processed) {
    showWarning('Some locations could not be saved due to GPS errors');
  }
}

// Celebrate discoveries regardless
if (response.discoveries.new_countries.length > 0) {
  showDiscoveryAnimation(response.discoveries.new_countries);
}
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| 100-location batch processing | < 500ms |
| Reverse geocoding (10 unique res-6 cells) | < 100ms |
| Bulk upsert (100 cells) | < 200ms |
| Achievement check | < 100ms |

---

## Future Considerations

### Not Included in MVP

1. **Server-side chunking**: Client handles >100 locations by sending multiple requests
2. **Resume tokens**: If a batch fails mid-sync, client retries entire batch
3. **Streaming uploads**: Overkill for current batch sizes

### Potential Future Enhancements

1. **Compression**: gzip request bodies for large batches
2. **Background processing**: Accept batch, return job ID, poll for results
3. **Webhooks**: Notify client of discoveries via push instead of response
