# projects_by_collection_v1

> Many-to-many mapping between projects and collections (ecosystems, funding rounds, categories).

## Quick Reference
- **Table**: `oso.projects_by_collection_v1`
- **Kind**: FULL
- **Grain**: (project_id, collection_id)
- **Tags**: export, entity_category=collection
- **Source SQL**: `warehouse/oso_sqlmesh/models/marts/entities/projects_by_collection_v1.sql`

## Schema
| Column | Type | Semantic Type | Description |
|--------|------|---------------|-------------|
| project_id | VARCHAR | ID | The unique identifier for the project. |
| project_source | VARCHAR | CATEGORICAL / DIMENSION | The source of the project, such as "OSS_DIRECTORY" or "OP_ATLAS". |
| project_namespace | VARCHAR | CATEGORICAL / DIMENSION | The namespace of the project within the source. |
| project_name | VARCHAR | CATEGORICAL / DIMENSION | The project slug (unique within a registry but not globally). |
| collection_id | VARCHAR | ID | The unique identifier for the collection. |
| collection_source | VARCHAR | CATEGORICAL / DIMENSION | The source of the collection, such as "OSS_DIRECTORY" or "OP_ATLAS". |
| collection_namespace | VARCHAR | CATEGORICAL / DIMENSION | The namespace of the collection within the source. |
| collection_name | VARCHAR | CATEGORICAL / DIMENSION | The name of the collection. |

## Column Statistics

| Column | Distinct | Null % | Min | Max | Sample Values |
|--------|----------|--------|-----|-----|---------------|
| project_id | thousands | 0% | — | — | hex hash |
| project_source | ~5 | 0% | — | — | `OSS_DIRECTORY`, `OP_ATLAS`, `DEFILLAMA`, `OPEN_LABELS_INITIATIVE` |
| project_name | thousands | 0% | — | — | `uniswap`, `aave`, `optimism` |
| collection_id | hundreds | 0% | — | — | hex hash |
| collection_source | ~5 | 0% | — | — | `OSS_DIRECTORY`, `OP_ATLAS`, `DEFILLAMA`, `OPEN_LABELS_INITIATIVE` |
| collection_name | hundreds | 0% | — | — | `optimism`, `ethereum`, `retro-funding-4` |

> Statistics are estimated from SQL logic — verify with `/oso-public-datasets-audit`.

## Column Relationships

- **(project_id, collection_id) is the natural key** — a project can belong to many collections and a collection can contain many projects.
- **`project_source` and `collection_source` are typically the same** — OSSD projects are grouped into OSSD collections, OP Atlas projects into OP Atlas collections, etc.
- **collection fields come from a LEFT JOIN to `int_collections`** — the mart enriches the raw mapping with collection metadata.

## Query Rules

### Filtering Rules

- **Filter by `collection_source = 'OSS_DIRECTORY'`** when working with OSSD ecosystem data. This ensures you only see OSSD-curated groupings and avoids mixing with OP Atlas funding rounds or DeFiLlama categories.
- **Filter by `collection_name`** to scope to a specific ecosystem or category (eg `WHERE collection_name = 'ethereum'`).
- **No partition filtering is available** — FULL table, all predicates are post-scan.

### Aggregation Rules

- **`COUNT(DISTINCT project_id)` per collection** to count projects in a collection.
- **`COUNT(DISTINCT collection_id)` per project** to count how many collections a project belongs to.
- **Always include source filters in aggregations** to avoid double-counting across registries.

### Join Rules

- **Join to `oso.projects_v1` on `project_id`** to get project display names and descriptions.
- **Join to `oso.collections_v1` on `collection_id`** to get collection display names and descriptions.
- **Join to `oso.artifacts_by_project_v1` on `project_id`** to find all artifacts for projects in a given collection.
- **Cardinality**: many-to-many. A single project may appear multiple times (once per collection membership).

### Common Patterns

**List all projects in an OSSD collection:**
```sql
SELECT
  project_id,
  project_name,
  collection_name
FROM oso.projects_by_collection_v1
WHERE collection_source = 'OSS_DIRECTORY'
  AND collection_name = 'ethereum'
```

**Find projects that belong to multiple OSSD collections:**
```sql
SELECT
  project_id,
  project_name,
  COUNT(DISTINCT collection_id) AS num_collections,
  ARRAY_AGG(collection_name) AS collections
FROM oso.projects_by_collection_v1
WHERE collection_source = 'OSS_DIRECTORY'
GROUP BY project_id, project_name
HAVING COUNT(DISTINCT collection_id) > 1
ORDER BY num_collections DESC
```

**Count projects per OSSD collection:**
```sql
SELECT
  collection_name,
  COUNT(DISTINCT project_id) AS project_count
FROM oso.projects_by_collection_v1
WHERE collection_source = 'OSS_DIRECTORY'
GROUP BY collection_name
ORDER BY project_count DESC
```

## Business Logic

This mart joins `int_projects_by_collection` (the raw many-to-many mapping) with `int_collections` (collection metadata) via a LEFT JOIN on `collection_id`. The raw mapping unions membership records from four registries:

- **OSS Directory** (`int_projects_by_collection_in_ossd`) — ecosystem and category groupings from YAML files
- **OP Atlas** (`int_projects_by_collection_in_op_atlas`) — Optimism funding round memberships
- **DeFiLlama** (`int_projects_by_collection_in_defillama`) — DeFi protocol categories
- **Open Labels Initiative** (`int_projects_by_collection_in_openlabelsinitiative`) — community-sourced groupings

There is no cross-source deduplication — a project in both OSSD and OP Atlas will appear under each source's collections separately.

## Lineage

### Upstream (direct)
- `oso.int_projects_by_collection` — raw many-to-many mapping from all sources
- `oso.int_collections` — collection metadata (LEFT JOIN)

### Downstream (known consumers)
- Collection-scoped analyses and dashboards
- Ecosystem membership reports

## Best Practices

- **Always filter by `collection_source = 'OSS_DIRECTORY'`** for OSSD ecosystem work. This is the most common use case and avoids mixing with other registries.
- **Use this table as the starting point for ecosystem analysis** — filter to a collection, then join to `artifacts_by_project_v1` for repos/contracts, and to metric tables for KPIs.
- **Be aware of many-to-many cardinality** — a project can appear in multiple collections, so joining without a collection filter will fan out rows.

## Metadata
- **Generated**: 2026-03-20
