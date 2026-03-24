# int_events__gitcoin_funding

> Intermediate table combining Gitcoin donation and matching events, enriched with OSO project mappings and chain metadata.

## Quick Reference
- **Table**: `oso.int_events__gitcoin_funding`
- **Kind**: FULL
- **Grain**: not declared (no unique key constraint; events can repeat across rounds)
- **Cron**: not specified (full refresh on pipeline run)
- **Tags**: funding
- **Source SQL**: `warehouse/oso_sqlmesh/models/intermediate/events/funding/gitcoin/int_events__gitcoin_funding.sql`

## Schema
| Column | Type | Semantic Type | Description |
|--------|------|---------------|-------------|
| time | TIMESTAMP | TIMESTAMP | Event timestamp (donation time, or round end time for matching events where timestamp is absent) |
| event_source | VARCHAR | CATEGORICAL | `GITCOIN_DONATIONS` or `GITCOIN_MATCHING` |
| gitcoin_group_project_name | VARCHAR | TEXT | Canonical group-level project name (groups related Gitcoin applications) |
| gitcoin_project_name | VARCHAR | TEXT | Individual Gitcoin application name |
| recipient_address | VARCHAR | ADDRESS | Address that received the funding |
| donor_address | VARCHAR | ADDRESS | Address of the donor; NULL for matching events |
| amount_in_usd | DOUBLE | METRIC | Funding amount in USD, already normalized |
| round_number | INTEGER | CATEGORICAL | Gitcoin round number |
| round_name | VARCHAR | CATEGORICAL | Human-readable round name |
| chain | VARCHAR | CATEGORICAL | Chain name where the funding occurred |
| chain_id | INTEGER | ID | Numeric chain ID |
| round_id | VARCHAR | ID | Gitcoin round identifier |
| gitcoin_group_id | VARCHAR | ID | Gitcoin group project identifier |
| gitcoin_project_id | VARCHAR | ID | Individual Gitcoin application identifier |
| oso_project_id | VARCHAR | ID | OSO project ID; nullable — not all Gitcoin projects are mapped |
| oso_project_name | VARCHAR | TEXT | OSO project name; nullable |

## Column Statistics

| Column | Distinct | Null % | Min | Max | Sample Values |
|--------|----------|--------|-----|-----|---------------|
| time | high | 0% | 2019 (early rounds) | now | — |
| event_source | 2 | 0% | — | — | `GITCOIN_DONATIONS`, `GITCOIN_MATCHING` |
| gitcoin_group_project_name | thousands | ~0% | — | — | `Uniswap`, `Protocol Guild` |
| gitcoin_project_name | thousands | ~0% | — | — | application-specific names |
| recipient_address | thousands | ~0% | — | — | lowercase hex |
| donor_address | millions | ~50% (NULL for all GITCOIN_MATCHING rows) | — | — | lowercase hex |
| amount_in_usd | high | 0% | >0 (filtered at ingest) | 10M+ (matching) | 1.0, 5.0, 100.0 |
| round_number | ~30 | 0% | 1 | 20+ | 14, 15, 16, 18, 19 |
| round_name | ~30 | ~0% | — | — | `GR15`, `Gitcoin Citizens Round` |
| chain | ~10 | ~0% | — | — | `ethereum`, `optimism`, `polygon` |
| chain_id | ~10 | 0% | 1 | 8453 | 1, 10, 137 |
| round_id | hundreds | 0% | — | — | UUIDs or addresses |
| gitcoin_group_id | thousands | 0% | — | — | UUIDs |
| gitcoin_project_id | thousands | 0% | — | — | UUIDs |
| oso_project_id | thousands | ~30–50% (unmapped projects) | — | — | OSO UUIDs |
| oso_project_name | thousands | ~30–50% | — | — | `uniswap`, `protocol-guild` |

> Statistics are estimated from SQL logic and known Gitcoin dataset characteristics — verify with `/oso-public-datasets-audit`.

## Column Relationships

- **`donor_address` is NULL when `event_source = 'GITCOIN_MATCHING'`** — matching allocations are protocol-level distributions with no individual donor. Any aggregation involving `donor_address` must account for this or filter to `GITCOIN_DONATIONS` only.
- **`oso_project_id` is NULL for unmapped projects** — the join to OSO uses `is_best_match = TRUE` via a LEFT JOIN, so Gitcoin projects without an OSO counterpart remain in the table with NULL OSO fields. This is a known coverage gap, not a data error.
- **`gitcoin_group_id` groups multiple `gitcoin_project_id` values** — one group can have several applications across rounds. Use `gitcoin_group_id` for stable project identity; use `gitcoin_project_id` for application-level granularity.
- **`(round_id, gitcoin_project_id, donor_address, time)` approximates row uniqueness for donations** — there is no declared unique key, but this combination should be near-unique for `GITCOIN_DONATIONS`. Matching rows are unique at `(round_id, gitcoin_project_id)`.
- **`chain` is derived from `chain_id`** — resolved via a join to `int_chainlist`. They are redundant; use `chain` for human-readable filters and `chain_id` for numeric joins.
- **Matching `time` values cluster at round boundaries** — when no explicit timestamp is available, the model assigns the round's maximum observed timestamp. Fine-grained time analysis of matching events will show artificial spikes at round end dates.

## Query Rules

### Filtering Rules

- **Filter by `event_source`** to separate donation flows from matching flows. They have fundamentally different semantics: `GITCOIN_DONATIONS` are individual contributor transfers; `GITCOIN_MATCHING` are protocol-level quadratic funding allocations.
- **Filter by `round_number`** to scope queries to specific funding rounds (e.g., `WHERE round_number = 19`).
- **No partition filtering is available** — this is a FULL refresh model. All time-range filters reduce returned rows but do not skip storage-layer scanning.
- **Handle NULL `oso_project_id`** explicitly — use `WHERE oso_project_id IS NOT NULL` to restrict to mapped projects, or use `COALESCE(oso_project_id, gitcoin_group_id)` to include unmapped projects under their Gitcoin identity.

### Aggregation Rules

- **Use `SUM(amount_in_usd)` for total funding** — values are pre-normalized; no conversion needed.
- **Use `COUNT(DISTINCT donor_address)` for unique donors** — meaningful only when filtered to `event_source = 'GITCOIN_DONATIONS'`. Including matching rows will undercount because `donor_address` is NULL for them.
- **Use `COALESCE` or filter NULLs when grouping on `oso_project_id`** — a bare `GROUP BY oso_project_id` will create a NULL bucket containing all unmapped projects lumped together.
- **GROUP BY `gitcoin_group_id`** (not `gitcoin_project_id`) for canonical per-project totals across rounds.

### Join Rules

- **Join to `oso.projects_v1` on `oso_project_id`** — use a LEFT JOIN and handle NULLs; a meaningful share of Gitcoin projects are not yet mapped to OSO.
- **Join to other funding tables on `recipient_address`** — suitable for cross-protocol funding analysis when OSO project mapping is unavailable.
- **Cardinality with `oso.projects_v1`**: many-to-one on `oso_project_id` (multiple funding events per project). The join does not fan out rows.
- **Do not join on `gitcoin_project_name` or `oso_project_name`** — use IDs for joins; names are display strings subject to formatting variation.

### Common Patterns

**Total funding by OSO project (donations + matching):**
```sql
SELECT
  COALESCE(oso_project_name, gitcoin_group_project_name) AS project_name,
  SUM(amount_in_usd) AS total_funding_usd,
  SUM(CASE WHEN event_source = 'GITCOIN_DONATIONS' THEN amount_in_usd ELSE 0 END) AS donations_usd,
  SUM(CASE WHEN event_source = 'GITCOIN_MATCHING' THEN amount_in_usd ELSE 0 END) AS matching_usd
FROM oso.int_events__gitcoin_funding
GROUP BY 1
ORDER BY total_funding_usd DESC
LIMIT 50
```

**Unique donors per project per round (donations only):**
```sql
SELECT
  round_number,
  COALESCE(oso_project_name, gitcoin_group_project_name) AS project_name,
  COUNT(DISTINCT donor_address) AS unique_donors,
  SUM(amount_in_usd) AS total_donated_usd
FROM oso.int_events__gitcoin_funding
WHERE event_source = 'GITCOIN_DONATIONS'
  AND round_number >= 15
GROUP BY round_number, project_name
ORDER BY round_number, unique_donors DESC
```

**Funding breakdown by round (donations vs matching):**
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

## Business Logic

This model unifies two distinct Gitcoin funding flows — direct donations from contributors and quadratic matching allocations from round pools — into a single event stream.

Donations are sourced directly from the raw donations staging table, filtered to rows with a positive USD amount. Matching allocations come from the matching staging table; because matching records sometimes lack an explicit timestamp, the model falls back to the round's end time (the maximum timestamp observed in the round) when no timestamp is available.

The two event types are union'd and then enriched in two passes. First, each event is linked back to an OSO project by walking a three-table chain: Gitcoin project ID → project group → OSO project mapping. Only the single best-match mapping is used (`is_best_match = TRUE`) when multiple candidates exist. This join is a LEFT JOIN, so events for Gitcoin projects with no OSO counterpart are still included with NULL OSO fields. Second, chain names are resolved by joining to `int_chainlist` on chain_id.

The net result is a flat event table that supports both Gitcoin-native analysis (using Gitcoin IDs and round metadata) and OSO cross-ecosystem analysis (using oso_project_id to join with other OSO models).

## Lineage

### Full Chain
```
bigquery.gitcoin.all_donations → oso.stg_gitcoin__all_donations ──┐
bigquery.gitcoin.all_matching → oso.stg_gitcoin__all_matching ────┤
oso.stg_gitcoin__project_lookup ──────────────────────────────────┤
oso.stg_gitcoin__project_groups_summary ──────────────────────────┼→ oso.int_events__gitcoin_funding
oso.int_project_to_projects__gitcoin ─────────────────────────────┤
oso.int_chainlist ────────────────────────────────────────────────┘
```

### Upstream (direct)
- `oso.stg_gitcoin__all_donations` — raw donation events with USD amounts
- `oso.stg_gitcoin__all_matching` — quadratic matching allocations per round
- `oso.stg_gitcoin__project_lookup` — maps application IDs to group IDs
- `oso.stg_gitcoin__project_groups_summary` — group-level project metadata
- `oso.int_project_to_projects__gitcoin` — bridge table mapping Gitcoin groups to OSO projects
- `oso.int_chainlist` — chain ID to chain name lookup

### Downstream (known consumers)
- Gitcoin funding event mart models (e.g., `oso.events_by_project_v1` funding slices)
- OSO metrics models aggregating funding received by project over time

## Best Practices

- **Filter by `event_source`** to separate donation flows from matching flows — they have different semantics, and `donor_address` is NULL for matching events.
- **Account for NULL `donor_address`** in aggregations over matching events. A `COUNT(donor_address)` will undercount; use `COUNT(*)` with an `event_source` filter instead.
- **Use `oso_project_id` for cross-model joins**, but always handle the NULL case — a meaningful share of Gitcoin projects are not (yet) mapped to OSO projects.
- **Prefer `gitcoin_group_project_name` as the display name** — it represents the canonical project identity across multiple Gitcoin rounds and applications, while `gitcoin_project_name` is application-specific.
- **Use `gitcoin_group_id` for Gitcoin-native aggregations** — it is the stable identifier across rounds for the same project.
- **`amount_in_usd` requires no conversion** — values are pre-normalized from the staging tables.
- **This is a FULL refresh model** — no partition filtering is available or needed, but be aware of full table scan cost on large time-range queries.
- **Matching timestamps default to round end time** — be cautious when doing fine-grained time analysis of matching events; many will cluster at round boundaries.

## Metadata
- **Generated**: 2026-03-10
- **Source commit**: 96a40d471
