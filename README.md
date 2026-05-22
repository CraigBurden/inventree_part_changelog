# InvenTree Part & Category Change Logger

[![InvenTree Version](https://img.shields.io/badge/InvenTree-%3E%3D0.12.0-blue)](https://inventree.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A powerful plugin for [InvenTree](https://inventree.org/) that captures granular lifecycle events for parts, part categories, and part parameters (creation, modifications, and deletions). All captured events are stored in a dedicated database log and can be retrieved via a fully-featured REST API endpoint. 

This plugin is especially useful for integration with external systems, change notification feeds, synchronization pipelines, or audit logging.

---

## Features

- **Automated Event Tracking**: Hooks directly into InvenTree's internal event-driven signal system.
- **Support for Key Models**:
  - **Parts** (`part_part.*`)
  - **Part Categories** (`part_partcategory.*`)
  - **Part Parameters** (`part_partparameter.*` / `part_parameter.*`)
- **Relational Context Resolution**: Automatically attempts to resolve and store the `related_part_id` and `related_category_id` at the time of the event. This ensures that even when a parameter is updated, you can instantly see which Part and Category are affected without extra database queries.
- **Log Retention Policy**: Includes built-in automatic background cleanup to purge logs older than a configurable number of days.
- **Advanced Query REST API**: Supports querying, date-range filtering, action/type filtering, and a high-performance **Concise Summary** mode with parent "bubble-up" intelligence.

---

## Installation & Setup

### 1. Install the Plugin

If you are running InvenTree in a virtual environment or docker setup, install the package in the same environment as InvenTree. For example, if you are developing locally:

```bash
pip install /path/to/inventree_part_changelog
```

Or reference it from your git repository in your `plugins.txt` file.

### 2. Enable Plugin in InvenTree

Ensure that plugin integration is enabled in your InvenTree configuration (typically `INVENTREE_PLUGINS_ENABLED=True` in your environment variables or defined in `config.yaml`).

1. Log into your InvenTree instance as an administrator.
2. Navigate to **Admin Center** -> **Plugins**.
3. Locate **PartChangeLog** in the inactive plugins list and activate it.
4. Restart your InvenTree server/worker processes to load the plugin.

### 3. Run Database Migrations

Because the plugin defines a custom database model (`PartChangeLogEntry`) to store log records safely, you need to run Django migrations:

```bash
python manage.py migrate inventree_part_changelog
```

---

## Configuration Settings

You can customize the plugin behavior directly from the **InvenTree Plugin Settings** interface:

| Setting Key | Label | Type | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `RETENTION_DAYS` | **Log Retention (Days)** | `Integer` | `0` | Number of days to retain logs before purging. Set to `0` to keep them indefinitely. |
| `TRACK_PARTS` | **Track Parts** | `Boolean` | `True` | Log events when parts are created, modified, or deleted. |
| `TRACK_CATEGORIES`| **Track Categories** | `Boolean` | `True` | Log events when part categories are created, modified, or deleted. |
| `TRACK_PARAMETERS`| **Track Parameters** | `Boolean` | `True` | Log events when part parameters are created, modified, or deleted. |

> [!NOTE]
> Log retention purging is run automatically in the background whenever a new tracked event is captured.

---

## How It Works Under the Hood

### Event Hooking
The plugin subclasses `EventMixin` and listens to InvenTree's system events. Whenever one of the following events triggers:
* `part_part.created`, `part_part.saved`, `part_part.deleted`
* `part_partcategory.created`, `part_partcategory.saved`, `part_partcategory.deleted`
* `part_partparameter.created` / `part_parameter.created` (and related `.saved` / `.deleted` events)

The plugin extracts the object identity (`id`), queries the database safely (if the item is not deleted) to identify parent associations, and logs the change to `PartChangeLogEntry`.

### Context Enrichment
For updates and creations, the plugin inspects the model instance to extract related keys:
* **For a parameter**: Resolves its owning Part ID.
* **For a part**: Resolves its parent Category ID.
This relational metadata is stored directly on the log row to allow highly optimized REST API filtering and summaries.

---

## REST API Endpoint

The plugin registers a custom REST API endpoint to retrieve and query log events.

* **URL**: `/api/plugin/partchangelog/logs/`
* **Method**: `GET`
* **Authentication**: Requires Django token or session authentication (identical to standard InvenTree API).

### Query Parameters

| Parameter | Type | Description | Example |
| :--- | :--- | :--- | :--- |
| `start` | `string` | **ISO 8601 Datetime**. Filter log entries created *on or after* this date. | `2026-05-22T00:00:00Z` |
| `end` | `string` | **ISO 8601 Datetime**. Filter log entries created *on or before* this date. | `2026-05-22T23:59:59Z` |
| `item_types`| `string` | **Comma-separated list**. Filter by specific model type(s). Supported values: `part`, `partcategory`, `partparameter`, `parameter`. | `part,partcategory` |
| `actions` | `string` | **Comma-separated list**. Filter by action type (e.g. `created`, `saved`, `deleted`). | `created,deleted` |
| `concise` | `boolean` | **Toggle summary response**. Set to `true` to return a grouped unique change-summary instead of a flat log list. Defaults to `false`. | `true` |

---

## Response Formats

### 1. Detailed Log Format (`concise=false`)

Ideal for detailed audit trailing or displaying chronological events step-by-step.

#### Example Request
`GET /api/plugin/partchangelog/logs/?item_types=part&actions=created`

#### Example Response
```json
{
  "count": 2,
  "logs": [
    {
      "id": 142,
      "item_type": "part",
      "item_id": 45,
      "action": "created",
      "related_part_id": null,
      "related_category_id": 12,
      "timestamp": "2026-05-22T19:45:00.123456+00:00"
    },
    {
      "id": 143,
      "item_type": "part",
      "item_id": 46,
      "action": "created",
      "related_part_id": null,
      "related_category_id": 12,
      "timestamp": "2026-05-22T19:48:22.987654+00:00"
    }
  ]
}
```

---

### 2. Concise Summary Format (`concise=true`)

Designed specifically for efficient downstream integrations (like cache synchronization). Rather than returning a lengthy chronological table, this mode groups unique object IDs that have been **updated** (created or saved) vs. those that have been **deleted**.

#### Parent Bubble-Up Intelligence
To optimize synchronization, the concise mode implements **bubble-up logic** for updates:
* **Parameter updates bubble up to their parent Part**: If a part parameter is added, updated, or saved, its related Part ID is automatically added to the `updated.parts` list.
* **Part updates bubble up to their parent Category**: If a part is added, updated, or saved, its related Category ID is automatically added to the `updated.categories` list.

This allows external integrations to query the API for a given timeframe, receive a clean checklist of unique Category and Part IDs affected, and refresh only those cache items.

#### Example Request
`GET /api/plugin/partchangelog/logs/?concise=true&start=2026-05-22T00:00:00Z`

#### Example Response
```json
{
  "concise": true,
  "summary": {
    "updated": {
      "parts": [45, 46, 89],
      "categories": [12, 15],
      "parameters": [104, 105]
    },
    "deleted": {
      "parts": [40],
      "categories": [],
      "parameters": [99]
    }
  }
}
```

---

## Contributors

* **Craig Burden** - Primary Author
* **Antigravity** - AI Pair Programmer

---

## License

This plugin is licensed under the [MIT License](LICENSE). Feel free to customize and integrate it as needed.
