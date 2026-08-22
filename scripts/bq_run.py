"""Run a .sql file against BigQuery via the Python client.

The `bq` CLI needs an interactive `gcloud auth login` when its token lapses;
the Python client picks up application-default credentials and keeps working,
so this is the reliable path from an automated session.

    python scripts/bq_run.py <file.sql> [--dry-run] [--json]
"""
import sys
from pathlib import Path
from google.cloud import bigquery


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    as_json = "--json" in sys.argv
    sql = Path(args[0]).read_text()

    client = bigquery.Client(project="bf-data-dev-qz06", location="EU")
    job = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=dry, use_query_cache=False))

    if dry:
        print(f"VALID — would process {job.total_bytes_processed / 1e9:.1f} GB")
        return

    rows = list(job.result())
    print(f"job {job.job_id} done; {job.total_bytes_processed / 1e9:.1f} GB processed")
    if not rows:
        return
    if as_json:
        import json
        print(json.dumps([dict(r) for r in rows], indent=1, default=str))
        return
    cols = list(rows[0].keys())
    w = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    print("  ".join(c.ljust(w[c]) for c in cols))
    print("  ".join("-" * w[c] for c in cols))
    for r in rows:
        print("  ".join(str(r[c]).ljust(w[c]) for c in cols))


if __name__ == "__main__":
    main()
