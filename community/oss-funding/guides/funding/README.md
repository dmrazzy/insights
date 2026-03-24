# Funding Data Guide

> Hub guide for all models related to grants and funding data in OSO — covering Gitcoin, oss-funding (Optimism, Octant, Stellar, Arbitrum, etc.), and Open Collective.

## What is OSO Funding Data?

OSO tracks grants and funding to open source projects from multiple sources:

1. **[oss-funding](https://github.com/opensource-observer/oss-funding)** — a curated GitHub repo of grant data with per-funder directories and a consolidated `data/funding_data.csv`. Covers Optimism (RetroPGF + Gov Grants), Octant (Epochs 1–9), Gitcoin (historical), Stellar, Arbitrum (STIP-1), CLR.fund, and DAO Drops.
2. **Gitcoin** — direct pipeline from Gitcoin's donation and matching data (separate from oss-funding).
3. **Open Collective** — expenses and deposits from Open Collective collectives (incremental pipeline).

All three sources are unified into `oso.int_events_daily__funding`, which is the primary table for cross-funder analysis.

## Data Pipeline

```
oss-funding repo (YAML + CSV)
  → bigquery.ossd.funding
    → oso.stg_ossd__current_funding
      → oso.int_events_daily__ossd_funding ──────────────────┐
                                                              │
Gitcoin raw data (donations + matching)                       │
  → oso.stg_gitcoin__all_donations                            │
  → oso.stg_gitcoin__all_matching                             │
    → oso.int_events__gitcoin_funding (enriched, per-event)   │
      → oso.int_events_daily__gitcoin_funding ────────────────┤
                                                              ├→ oso.int_events_daily__funding
Open Collective (expenses + deposits)                         │
  → oso.stg_open_collective__expenses                         │
  → oso.stg_open_collective__deposits                         │
    → oso.int_events__open_collective_funding (incremental)   │
      → oso.int_events_daily__open_collective_funding ────────┘
```

## Event Sources

All funding flows into `int_events_daily__funding` with these `event_source` values:

| event_source | Origin | Notes |
|-------------|--------|-------|
| `OPEN_COLLECTIVE` | Open Collective pipeline | Includes CREDIT and DEBIT events — dominates row count |
| `GITCOIN_DONATIONS` | Gitcoin pipeline | Individual donor contributions |
| `GITCOIN_MATCHING` | Gitcoin pipeline | Quadratic matching allocations |
| `OPTIMISM_RETROFUNDING` | oss-funding repo | RetroPGF rounds |
| `OPTIMISM_GOVGRANTS` | oss-funding repo | Optimism governance grants (seasons) |
| `STELLAR` | oss-funding repo | Stellar Community Fund |
| `OCTANT` | oss-funding repo | Golem Foundation epochs |
| `ARBITRUMFOUNDATION` | oss-funding repo | STIP-1 |
| `CLRFUND` | oss-funding repo | CLR.fund rounds |
| `DAODROPS` | oss-funding repo | DAO Drops |

> New funders may be added to oss-funding over time. Run `/oso-public-datasets-audit` for current counts.

## Event Types

| event_type | Source | Description |
|------------|--------|-------------|
| `CREDIT` | Open Collective | Incoming funds to a collective |
| `DEBIT` | Open Collective | Outgoing expenses from a collective |
| `FUNDING_AWARDED` | oss-funding + Gitcoin | Grant awarded to a project |

## Model Reference

| Model | Guide | Grain | Description |
|-------|-------|-------|-------------|
| `oso.int_events_daily__funding` | [int_events_daily__funding.md](int_events_daily__funding.md) | (bucket_day, event_source, event_type, from_artifact_id, to_artifact_id) | **Primary table**: all funding events unified, daily aggregated |
| `oso.int_events_daily__ossd_funding` | [int_events_daily__ossd_funding.md](int_events_daily__ossd_funding.md) | (bucket_day, event_source, event_type, from_artifact_id, to_artifact_id) | oss-funding repo data only (Optimism, Octant, Stellar, etc.) |
| `oso.stg_ossd__current_funding` | [stg_ossd__current_funding.md](stg_ossd__current_funding.md) | per-grant row | Raw oss-funding CSV with grant pool names, metadata, application URLs — fields lost downstream |
| `oso.int_events__gitcoin_funding` | [int_events__gitcoin_funding.md](int_events__gitcoin_funding.md) | per-event (no declared key) | Gitcoin donations + matching, enriched with OSO project mappings |

## ID Generation

Funding models use `@oso_entity_id` to generate artifact IDs for both funders and recipients:

- **`to_artifact_id`** = `@oso_entity_id('OSS_DIRECTORY', 'oso', to_project_name)` — the funded project
- **`from_artifact_id`** = `@oso_entity_id('OSS_DIRECTORY', 'oso', from_funder_name)` — the funder

These IDs match `project_id` values in `oso.projects_v1` when `project_source = 'OSS_DIRECTORY'`. For Gitcoin projects without an OSO mapping, `to_artifact_id` falls back to `@oso_entity_id('GITCOIN', '', recipient_address)`.

## Common Query Patterns

### Total funding by project across all sources

```sql
SELECT
  p.project_name,
  p.display_name,
  f.event_source,
  SUM(f.amount) AS total_funding_usd
FROM oso.int_events_daily__funding AS f
INNER JOIN oso.projects_v1 AS p
  ON f.to_artifact_id = p.project_id
WHERE p.project_source = 'OSS_DIRECTORY'
  AND f.event_type = 'FUNDING_AWARDED'
GROUP BY p.project_name, p.display_name, f.event_source
ORDER BY total_funding_usd DESC
LIMIT 50
```

### Funder × category matrix (for ETHMapper)

```sql
SELECT
  f.event_source AS funder,
  c.collection_name AS category,
  COUNT(DISTINCT f.to_artifact_id) AS project_count,
  SUM(f.amount) AS total_funding_usd
FROM oso.int_events_daily__funding AS f
INNER JOIN oso.projects_v1 AS p
  ON f.to_artifact_id = p.project_id
INNER JOIN oso.projects_by_collection_v1 AS c
  ON p.project_id = c.project_id
WHERE p.project_source = 'OSS_DIRECTORY'
  AND c.collection_source = 'OSS_DIRECTORY'
  AND f.event_type = 'FUNDING_AWARDED'
GROUP BY f.event_source, c.collection_name
ORDER BY total_funding_usd DESC
```

### Funding timeline by source

```sql
SELECT
  DATE_TRUNC('MONTH', f.bucket_day) AS month,
  f.event_source,
  SUM(f.amount) AS monthly_funding_usd,
  COUNT(DISTINCT f.to_artifact_id) AS projects_funded
FROM oso.int_events_daily__funding AS f
WHERE f.event_type = 'FUNDING_AWARDED'
GROUP BY 1, 2
ORDER BY 1, 2
```

### Join funding with repo/dependency data

```sql
SELECT
  p.project_name,
  SUM(f.amount) AS total_funding_usd,
  COUNT(DISTINCT r.artifact_id) AS repo_count,
  SUM(r.star_count) AS total_stars
FROM oso.int_events_daily__funding AS f
INNER JOIN oso.projects_v1 AS p
  ON f.to_artifact_id = p.project_id
INNER JOIN oso.artifacts_by_project_v1 AS a
  ON p.project_id = a.project_id
INNER JOIN oso.repositories_v0 AS r
  ON a.artifact_id = r.artifact_id
WHERE p.project_source = 'OSS_DIRECTORY'
  AND a.project_source = 'OSS_DIRECTORY'
  AND a.artifact_source = 'GITHUB'
  AND f.event_type = 'FUNDING_AWARDED'
GROUP BY p.project_name
ORDER BY total_funding_usd DESC
LIMIT 30
```

## Gotchas

- **Always filter `event_type = 'FUNDING_AWARDED'` for grant analysis** — Open Collective contributes CREDIT and DEBIT events that represent general treasury flows, not grants. Without this filter, Open Collective dominates the row count (~95% of all rows).
- **Always filter `project_source = 'OSS_DIRECTORY'`** when joining to `projects_v1` — funding `to_artifact_id` values are generated from OSSD project names and will only match OSSD project IDs.
- **Octant data** lives in oss-funding under `data/funders/octant-golem-foundation/`. Query with `event_source = 'OCTANT'`.
- **Amounts are USD-equivalent at time of award** — no real-time price adjustments. For crypto-denominated grants, the USD value was set at award time.
- **`from_funder_name` maps to funder slugs** in oss-directory — the funder entity is treated as a project in the OSSD namespace for ID generation purposes.
- **Gitcoin has two pipelines** — oss-funding contains historical Gitcoin data as static CSV, while the Gitcoin pipeline has per-donation granularity with donor addresses. The daily unified table deduplicates by aggregating to (day, source, type, from, to).
- **Open Collective is incremental** — it refreshes daily. OSSD funding and Gitcoin are FULL refresh.
- **Coverage gaps** — not all funders are in oss-funding yet. The 7 current funders cover the major public goods funding sources but are not exhaustive.

## Metadata
- **Generated**: 2026-03-20
- **Source repos**: [oss-funding](https://github.com/opensource-observer/oss-funding), [kuma](https://github.com/opensource-observer/kuma) (pipeline)
