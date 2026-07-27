---
name: databricks-pipeline
description: Databricks pipeline patterns for Unity Catalog, UC Volumes, Asset Bundles, Delta tables, and Databricks Apps. Use when building pipelines, deploying jobs, managing data on Databricks, or working with databricks.yml bundles.
---

# Databricks Pipeline Patterns

## Unity Catalog Structure

```
catalog.schema.table          -- fully qualified table name
/Volumes/catalog/schema/vol/  -- UC Volume path for files

# Common pattern for dev/prod separation
mdna_dev.pallet_pipeline.*    -- dev environment
bci_rbs_prod.curated.*        -- production
```

## Asset Bundles (databricks.yml)

```yaml
bundle:
  name: my-pipeline

workspace:
  host: ${DATABRICKS_HOST}

resources:
  jobs:
    my_job:
      name: "My Pipeline Job"
      schedule:
        quartz_cron_expression: "0 0 8 * * ?"
        timezone_id: "Europe/London"
      tasks:
        - task_key: main_task
          notebook_task:
            notebook_path: /Workspace/Users/user@company.com/pipeline/job
          existing_cluster_id: ${var.cluster_id}

variables:
  cluster_id:
    description: "Cluster ID"
    default: ""

targets:
  dev:
    default: true
```

Deploy: `databricks bundle deploy -t dev --profile DEFAULT`
Validate: `databricks bundle validate --profile DEFAULT`

## Delta Table Patterns

```sql
-- Create with comments for documentation
CREATE TABLE IF NOT EXISTS catalog.schema.my_table (
    id          STRING    COMMENT 'Unique identifier',
    status      STRING    COMMENT 'processing | success | failed',
    created_at  TIMESTAMP COMMENT 'Row insertion time'
) USING DELTA
COMMENT 'Description of table purpose';

-- Grant access to Apps service principal
GRANT SELECT ON TABLE catalog.schema.my_table TO `app-XXXXX agent-contract`;
```

## UC Volume File Operations

```python
from databricks.sdk import WorkspaceClient
import io

wc = WorkspaceClient()

# Write file to volume
wc.files.upload("/Volumes/catalog/schema/vol/file.json",
                io.BytesIO(data), overwrite=True)

# Read file from volume
resp = wc.files.download("/Volumes/catalog/schema/vol/file.json")
content = resp.contents.read()
```

## Databricks Apps (Streamlit)

```python
import os
import streamlit as st
from databricks.sdk import WorkspaceClient

wc = WorkspaceClient(
    host=os.environ.get("DATABRICKS_HOST"),
    token=os.environ.get("DATABRICKS_TOKEN"),
)

st.set_page_config(page_title="My App", layout="wide")
st.title("My App")

# Read data from UC Volume
resp = wc.files.download("/Volumes/catalog/schema/vol/data.json")
data = resp.contents.read()
```

App config (`app.yaml`):
```yaml
command:
  - streamlit
  - run
  - streamlit_app.py
  - --server.port
  - "8000"
env:
  - name: DATABRICKS_HOST
    valueFrom: DATABRICKS_HOST
  - name: DATABRICKS_TOKEN
    valueFrom: DATABRICKS_TOKEN
```

Deploy: `databricks apps deploy my-app --profile DEFAULT --source-code-path my-app/`

## Pipeline Job Pattern

```python
def main():
    wc = WorkspaceClient()
    spark = get_spark()

    # 1. Detect new data
    new_items = detect_new_items(spark)

    # 2. Process (SQL or Python)
    enriched_df = spark.sql(query)
    enriched_pandas = enriched_df.toPandas()

    # 3. Generate outputs (Excel/JSON to UC Volume)
    write_volume_file(wc, output_path, data)

    # 4. Write manifest for downstream consumers
    write_manifest(wc, manifest_path, metadata)
```

## CLI Quick Reference

```bash
databricks clusters list --profile DEFAULT
databricks apps list --profile DEFAULT
databricks apps deploy <name> --profile DEFAULT
databricks bundle validate --profile DEFAULT
databricks bundle deploy -t dev --profile DEFAULT
```
