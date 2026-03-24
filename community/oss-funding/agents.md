# OSO agent guide — OSS funding & OSS Directory

You are a data analyst with access to the OSO data warehouse. This document is the single entry point for **funding analysis** and **OSS Directory (OSSD)** joins in this repo. Deep model docs, pipeline diagrams, and extra query patterns live under [`guides/`](guides/).

---

## Documentation map (`guides/`)

Use these when you need grain, columns, lineage, or extended patterns beyond this page.

### Hub guides

| Topic | Guide |
|--------|--------|
| Grants & funding (pipeline, event sources, gotchas) | [`guides/funding/README.md`](guides/funding/README.md) |
| OSS Directory registry (projects, collections, repos, SBOMs) | [`guides/oss-directory/README.md`](guides/oss-directory/README.md) |

### Funding models

| Model | Guide |
|--------|--------|
| `oso.int_events_daily__funding` | [`guides/funding/int_events_daily__funding.md`](guides/funding/int_events_daily__funding.md) |
| `oso.int_events_daily__ossd_funding` | [`guides/funding/int_events_daily__ossd_funding.md`](guides/funding/int_events_daily__ossd_funding.md) |
| `oso.stg_ossd__current_funding` | [`guides/funding/stg_ossd__current_funding.md`](guides/funding/stg_ossd__current_funding.md) |
| `oso.int_events__gitcoin_funding` | [`guides/funding/int_events__gitcoin_funding.md`](guides/funding/int_events__gitcoin_funding.md) |

### OSS Directory models (join targets for funding)

| Model | Guide |
|--------|--------|
| `oso.collections_v1` | [`guides/oss-directory/collections_v1.md`](guides/oss-directory/collections_v1.md) |
| `oso.projects_v1` | [`guides/oss-directory/projects_v1.md`](guides/oss-directory/projects_v1.md) |
| `oso.projects_by_collection_v1` | [`guides/oss-directory/projects_by_collection_v1.md`](guides/oss-directory/projects_by_collection_v1.md) |
| `oso.artifacts_by_project_v1` | [`guides/oss-directory/artifacts_by_project_v1.md`](guides/oss-directory/artifacts_by_project_v1.md) |
| `oso.repositories_v0` | [`guides/oss-directory/repositories_v0.md`](guides/oss-directory/repositories_v0.md) |
| `oso.sboms_v0` | [`guides/oss-directory/sboms_v0.md`](guides/oss-directory/sboms_v0.md) |
| `oso.package_owners_v0` | [`guides/oss-directory/package_owners_v0.md`](guides/oss-directory/package_owners_v0.md) |

---

## Connection

Install pyoso and set your API key:

```bash
uv add pyoso  # or: pip install pyoso
export OSO_API_KEY=<your_key>
```

Query the warehouse:

```python
from pyoso import Client
client = Client()  # reads OSO_API_KEY from environment
df = client.to_pandas("SELECT * FROM oso.projects_v1 LIMIT 10")
```

Sign up at [oso.xyz/start](https://www.oso.xyz/start) for a free API key.

---

## SQL dialect

Use **Trino SQL**:

- `CAST(x AS VARCHAR)` not `SAFE_CAST`
- `DATE_TRUNC('month', dt)` not `DATE_TRUNC(dt, MONTH)`
- `COALESCE` not `IFNULL`
- `CURRENT_DATE - INTERVAL '30' DAY` for date math

---

## Key tables for funding analysis

| Table | Role |
|-------|------|
| `oso.int_events_daily__funding` | **Primary table**: all funding events unified, daily aggregated. Filter `event_type = 'FUNDING_AWARDED'` for grants. See [`guides/funding/int_events_daily__funding.md`](guides/funding/int_events_daily__funding.md). |
| `oso.int_events__gitcoin_funding` | Gitcoin donations + matching with round details, donor addresses, per-event granularity. See [`guides/funding/int_events__gitcoin_funding.md`](guides/funding/int_events__gitcoin_funding.md). |
| `oso.stg_ossd__current_funding` | Raw grant rows from oss-funding (pool names, metadata, URLs). See [`guides/funding/stg_ossd__current_funding.md`](guides/funding/stg_ossd__current_funding.md). |
| `oso.projects_v1` | Project registry. Join on `to_artifact_id = project_id` with `project_source = 'OSS_DIRECTORY'`. See [`guides/oss-directory/projects_v1.md`](guides/oss-directory/projects_v1.md). |
| `oso.projects_by_collection_v1` | Projects grouped by ecosystem/collection. See [`guides/oss-directory/projects_by_collection_v1.md`](guides/oss-directory/projects_by_collection_v1.md). |

Full pipeline and `event_source` / `event_type` semantics: [`guides/funding/README.md`](guides/funding/README.md).

---

## Funding sources (`event_source` values)

Grant-focused sources (typical for `event_type = 'FUNDING_AWARDED'`):

| event_source | Type | Description |
|-------------|------|-------------|
| `OPTIMISM_RETROFUNDING` | Retroactive | Optimism RetroPGF rounds |
| `OPTIMISM_GOVGRANTS` | Direct | Optimism governance grants (seasons) |
| `GITCOIN_DONATIONS` | Quadratic | Individual Gitcoin donor contributions |
| `GITCOIN_MATCHING` | Quadratic | Quadratic matching allocations |
| `ARBITRUMFOUNDATION` | Direct | Arbitrum STIP-1 |
| `STELLAR` | Direct | Stellar Community Fund |
| `OCTANT` | Direct | Golem Foundation epochs |
| `CLRFUND` | Quadratic | CLR.fund rounds |
| `DAODROPS` | Direct | DAO Drops |

`int_events_daily__funding` also includes **`OPEN_COLLECTIVE`** (and Open Collective `CREDIT` / `DEBIT` event types). For grant-style analysis, **always** filter `event_type = 'FUNDING_AWARDED'` so Open Collective treasury flows do not dominate. Details: [`guides/funding/README.md`](guides/funding/README.md).

---

## Starter queries

**Total retro funding YoY:**

```sql
SELECT
    YEAR(bucket_day) AS year,
    SUM(amount) AS total_usd,
    COUNT(DISTINCT to_artifact_id) AS projects_funded
FROM oso.int_events_daily__funding
WHERE event_type = 'FUNDING_AWARDED'
    AND event_source = 'OPTIMISM_RETROFUNDING'
GROUP BY YEAR(bucket_day)
ORDER BY year
```

**Total quadratic funding YoY (Gitcoin donations + matching):**

```sql
SELECT
    YEAR(bucket_day) AS year,
    SUM(amount) AS total_usd,
    COUNT(DISTINCT to_artifact_id) AS projects_funded
FROM oso.int_events_daily__funding
WHERE event_type = 'FUNDING_AWARDED'
    AND event_source IN ('GITCOIN_DONATIONS', 'GITCOIN_MATCHING', 'CLRFUND')
GROUP BY YEAR(bucket_day)
ORDER BY year
```

**All funding by source and year:**

```sql
SELECT
    event_source,
    YEAR(bucket_day) AS year,
    SUM(amount) AS total_usd,
    COUNT(DISTINCT to_artifact_id) AS projects_funded
FROM oso.int_events_daily__funding
WHERE event_type = 'FUNDING_AWARDED'
    AND bucket_day >= DATE '2019-01-01'
GROUP BY event_source, YEAR(bucket_day)
ORDER BY event_source, year
```

**Top funded projects:**

```sql
SELECT
    p.project_name,
    p.display_name,
    SUM(f.amount) AS total_funding_usd,
    COUNT(DISTINCT f.event_source) AS num_funders
FROM oso.int_events_daily__funding AS f
INNER JOIN oso.projects_v1 AS p
    ON f.to_artifact_id = p.project_id
WHERE p.project_source = 'OSS_DIRECTORY'
    AND f.event_type = 'FUNDING_AWARDED'
GROUP BY p.project_name, p.display_name
ORDER BY total_funding_usd DESC
LIMIT 30
```

**Gitcoin donations vs matching by round:**

```sql
SELECT
    round_number,
    round_name,
    SUM(CASE WHEN event_source = 'GITCOIN_DONATIONS' THEN amount_in_usd ELSE 0 END) AS donations_usd,
    SUM(CASE WHEN event_source = 'GITCOIN_MATCHING' THEN amount_in_usd ELSE 0 END) AS matching_usd,
    COUNT(DISTINCT CASE WHEN event_source = 'GITCOIN_DONATIONS' THEN donor_address END) AS unique_donors
FROM oso.int_events__gitcoin_funding
GROUP BY round_number, round_name
ORDER BY round_number
```

More patterns (funder × category, timelines, funding + repos): [`guides/funding/README.md`](guides/funding/README.md). OSSD hierarchy and supply-chain examples: [`guides/oss-directory/README.md`](guides/oss-directory/README.md).

---

## Important notes

- **Always filter `event_type = 'FUNDING_AWARDED'`** when using `int_events_daily__funding` for grant analysis — without this, Open Collective treasury flows dominate.
- **Always filter `project_source = 'OSS_DIRECTORY'`** when joining to `projects_v1` (and use the analogous `collection_source` / `artifact_source` filters when using other OSSD tables). See [`guides/oss-directory/README.md`](guides/oss-directory/README.md).
- **Amounts are USD** at time of award — no real-time price adjustments.
- **Only `oso.*` tables are publicly accessible.** Other namespaces require customer API keys.
