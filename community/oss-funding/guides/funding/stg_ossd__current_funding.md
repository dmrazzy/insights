# stg_ossd__current_funding

> Staging table for the oss-funding CSV — the richest view of grant data with project names, grant pool names, metadata (application URLs, token amounts), and file provenance. Fields lost in downstream models.

## Quick Reference
- **Table**: `oso.stg_ossd__current_funding`
- **Kind**: FULL
- **Grain**: per-grant row (no declared key)
- **Tags**: (none)
- **Source SQL**: `warehouse/oso_sqlmesh/models/staging/oss-directory/stg_ossd__current_funding.sql`

## Schema
| Column | Type | Semantic Type | Description |
|--------|------|---------------|-------------|
| to_project_name | VARCHAR | CATEGORICAL / DIMENSION | The OSSD project slug that received the grant (lowercased). Joinable to `projects_v1.project_name` where `project_source = 'OSS_DIRECTORY'`. |
| amount | DOUBLE | METRIC | Funding amount in USD at time of award. Defaults to 0.0 if unparseable. |
| funding_date | TIMESTAMP(6) | TIMESTAMP | Date the funding was awarded. Defaults to 1970-01-01 if unparseable. |
| from_funder_name | VARCHAR | CATEGORICAL / DIMENSION | The funder slug (lowercased). Maps to event_source in downstream models. |
| grant_pool_name | VARCHAR | CATEGORICAL / DIMENSION | The specific round, season, or epoch (lowercased). **Not carried downstream** — this is the only table with per-pool granularity. |
| metadata | VARCHAR | JSON | JSON string with application details. **Not carried downstream.** Typical fields: `application_name`, `application_url`, `token_amount`, `token_unit`. |
| file_path | VARCHAR | TEXT | Path to the source CSV in the oss-funding repo (eg `data/funders/stellar/uploads/scf-23.csv`). **Not carried downstream.** |

## Why Use This Table?

The downstream `int_events_daily__ossd_funding` and `int_events_daily__funding` models aggregate and hash away most of the context from this table. Use this staging table when you need:

- **Grant pool / round granularity** — `grant_pool_name` distinguishes `retropgf3` from `retrofunding4`, `epoch_8` from `epoch_9`, `grants_season_5` from `grants_season_6`, etc.
- **Application metadata** — `metadata` contains the original application name, URL, and native token amounts (eg `token_amount: 774829.1, token_unit: XLM`).
- **Human-readable names** — `to_project_name` and `from_funder_name` are the original slugs, not hashed IDs.
- **Source provenance** — `file_path` traces each row back to the exact CSV in the oss-funding repo.

## Column Statistics

| Column | Distinct | Null % | Min | Max | Sample Values |
|--------|----------|--------|-----|-----|---------------|
| to_project_name | thousands | 0% | — | — | `uniswap`, `protocol-guild`, `optimism` |
| amount | wide range | 0% | 0.0 | millions | 50000.0, 100000.0, 1000000.0 |
| funding_date | hundreds | 0% | ~2020 | 2025+ | timestamps |
| from_funder_name | 6 | 0% | — | — | `optimism`, `stellar`, `octant-golemfoundation`, `arbitrumfoundation`, `clrfund`, `dao-drops-dorgtech` |
| grant_pool_name | 59 | 0% | — | — | `retropgf3`, `retrofunding4`, `epoch_8`, `scf-23`, `stip-1`, `grants_season_5` |
| metadata | thousands | 0% | — | — | JSON strings |
| file_path | ~30 | 0% | — | — | `data/funders/stellar/uploads/scf-23.csv` |

> Statistics from live audit on 2026-03-20 (5,071 rows, 0% nulls on all columns).

## Grant Pool Breakdown

| Funder | Pool Pattern | Pools | Grants | Total USD |
|--------|-------------|-------|--------|-----------|
| Optimism | `retropgf*`, `retrofunding*` | 8 | ~3K | $156M |
| Optimism | `grants_season_*`, `missions_*` | 9 | ~580 | $113M |
| Arbitrum Foundation | `stip-1` | 1 | 56 | $123M |
| Stellar | `scf-*` | 10+ | ~550 | $34M |
| Octant | `epoch_*` | 9 | ~200 | $7.5M |
| CLR.fund | `round_*` | 1 | 80 | $83K |
| DAO Drops | `round_1` | 1 | 57 | $250K |

## Query Rules

### Filtering Rules

- **Filter by `from_funder_name`** for funder-specific analysis.
- **Filter by `grant_pool_name`** for round/epoch-specific analysis (eg `WHERE grant_pool_name = 'retropgf3'`).
- **Use `LIKE` patterns** for groups of pools: `WHERE grant_pool_name LIKE 'retrofunding%'` for all RetroPGF rounds.

### Join Rules

- **Join to `oso.projects_v1` on `to_project_name = project_name`** with `WHERE project_source = 'OSS_DIRECTORY'` for project metadata. This is a name-based join (not ID-based) since this staging table has raw names.
- **Join to `oso.artifacts_by_project_v1`** via `projects_v1` to get repos/contracts for funded projects.

### Common Patterns

**Funding by grant pool for a specific funder:**
```sql
SELECT
  grant_pool_name,
  COUNT(*) AS grant_count,
  SUM(amount) AS total_usd,
  COUNT(DISTINCT to_project_name) AS projects_funded,
  MIN(funding_date) AS earliest,
  MAX(funding_date) AS latest
FROM oso.stg_ossd__current_funding
WHERE from_funder_name = 'optimism'
GROUP BY grant_pool_name
ORDER BY total_usd DESC
```

**Extract metadata for a specific round:**
```sql
SELECT
  to_project_name,
  amount,
  funding_date,
  JSON_EXTRACT_SCALAR(metadata, '$.application_name') AS application_name,
  JSON_EXTRACT_SCALAR(metadata, '$.application_url') AS application_url,
  JSON_EXTRACT_SCALAR(metadata, '$.token_amount') AS token_amount,
  JSON_EXTRACT_SCALAR(metadata, '$.token_unit') AS token_unit
FROM oso.stg_ossd__current_funding
WHERE grant_pool_name = 'retropgf3'
ORDER BY amount DESC
```

**All Octant epochs with token details:**
```sql
SELECT
  grant_pool_name AS epoch,
  COUNT(*) AS projects_funded,
  SUM(amount) AS total_usd,
  JSON_EXTRACT_SCALAR(metadata, '$.token_unit') AS token_unit
FROM oso.stg_ossd__current_funding
WHERE from_funder_name = 'octant-golemfoundation'
GROUP BY grant_pool_name, JSON_EXTRACT_SCALAR(metadata, '$.token_unit')
ORDER BY grant_pool_name
```

**Projects funded by multiple funders (cross-funder overlap):**
```sql
SELECT
  to_project_name,
  COUNT(DISTINCT from_funder_name) AS num_funders,
  ARRAY_AGG(DISTINCT from_funder_name) AS funders,
  SUM(amount) AS total_usd
FROM oso.stg_ossd__current_funding
GROUP BY to_project_name
HAVING COUNT(DISTINCT from_funder_name) > 1
ORDER BY num_funders DESC, total_usd DESC
LIMIT 30
```

## Business Logic

This staging table reads directly from `bigquery.ossd.funding` via the `@oso_source` macro. The Dagster pipeline (`ossd.py`) fetches the consolidated `data/funding_data.csv` from the [oss-funding repo](https://github.com/opensource-observer/oss-funding) and loads it into BigQuery.

Transformations applied:
- **`to_project_name` and `from_funder_name`** are lowercased
- **`amount`** is cast to DOUBLE with a 0.0 fallback via `TRY_CAST`
- **`funding_date`** is parsed with multiple format attempts, defaulting to 1970-01-01 on failure
- **`metadata` and `file_path`** are passed through unchanged

No aggregation, hashing, or ID generation happens at this layer — those transformations occur in the downstream `int_events_daily__ossd_funding` model.

## Lineage

### Full Chain
```
oss-funding repo (data/funding_data.csv)
  → Dagster ossd.funding asset
    → bigquery.ossd.funding
      → oso.stg_ossd__current_funding     ← YOU ARE HERE
        → oso.int_events_daily__ossd_funding
          → oso.int_events_daily__funding
```

### Upstream (direct)
- `bigquery.ossd.funding` — raw CSV data loaded by Dagster

### Downstream (direct)
- `oso.int_events_daily__ossd_funding` — transforms to daily event format, generates entity IDs, drops metadata/pool/filepath

## Best Practices

- **Use this table for exploratory analysis** where you need grant pool names, metadata, or application URLs. For production queries that join to the broader OSO ecosystem, use `int_events_daily__funding` instead.
- **Parse metadata with `JSON_EXTRACT_SCALAR`** — the field is a JSON string, not a structured type.
- **Join on `to_project_name = project_name`** (not IDs) — this is a staging table with raw names.
- **Watch for 1970-01-01 dates** — these indicate unparseable `funding_date` values in the source CSV.
- **This is a FULL refresh table** — data reflects the latest state of the oss-funding repo.

## Metadata
- **Generated**: 2026-03-20
- **Source repo**: [oss-funding](https://github.com/opensource-observer/oss-funding)
