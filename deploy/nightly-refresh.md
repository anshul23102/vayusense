# Nightly archive refresh

VayuSense's processed archive (`data/processed/*.parquet`) is baked into the
Docker image at build time, so without this pipeline it silently stops
advancing the moment the image stops being rebuilt -- exactly what happened
before this was set up (the calendar had no 2026 data until manually fixed).

## Architecture

```
Cloud Scheduler (vayusense-nightly-refresh, 22:30 UTC daily)
        |  OAuth token as vayusense-scheduler@ (may only invoke this one job)
        v
Cloud Run Jobs API :run  ->  vayusense-refresh job (runs as vayusense-refresh@)
        |  runs benchmark/refresh_incremental.py
        v
downloads current parquet from gs://vayusense-data/processed/
        |
        v
finds each city's last archived date, fetches only NEW OpenAQ archive days
(usually zero -- the archive itself lags real time by ~4-5 days)
        |
        v
uploads refreshed parquet back to gs://vayusense-data/processed/
```

The running web service (`vayusense`) never gets redeployed by this
pipeline. Instead, `app/data_sync.py`'s `maybe_refresh()` is called from a
FastAPI middleware (`app/main.py`'s `sync_processed_data`) on every request,
TTL-gated to once per 3 hours: if the bucket has newer files, it downloads
them into `data/processed/` and calls `invalidate_all_caches()` so the next
request sees fresh data -- no restart needed.

This is deliberately request-triggered rather than a free-running background
thread: Cloud Run only allocates CPU during request handling by default, so
a thread trying to run on its own timer between requests stalls
indefinitely. That was tried first, silently didn't work, and was replaced
with this middleware approach after being caught by live testing.

## Resources created (one-time setup, already done)

- GCS bucket: `gs://vayusense-data` (seeded from the local processed parquet)
- Cloud Run Job: `vayusense-refresh`, same image as the web service, command
  overridden to `python -m benchmark.refresh_incremental`
- Cloud Scheduler job: `vayusense-nightly-refresh`, cron `30 22 * * *` (UTC),
  HTTP target hitting the Cloud Run Jobs v2 REST API's `:run` method
- IAM (least privilege, two dedicated accounts; see
  `deploy/harden_refresh_sa.sh`, which sets all of this up):
  - `vayusense-refresh@gen-lang-client-0133314577.iam.gserviceaccount.com`
    is the job's runtime identity, with `roles/storage.objectUser` on
    `gs://vayusense-data` only (read/write the parquet, nothing else)
  - `vayusense-scheduler@gen-lang-client-0133314577.iam.gserviceaccount.com`
    only triggers the job: `roles/run.invoker` on the `vayusense-refresh`
    job alone, no storage access at all
  - The Cloud Scheduler service agent
    (`service-663068003180@gcp-sa-cloudscheduler.iam.gserviceaccount.com`)
    holds `roles/iam.serviceAccountTokenCreator` on the scheduler account
    only, so Scheduler can mint an OAuth token as it when calling the Jobs API
  - The default Compute Engine account is deliberately NOT used: it is the
    broadest identity in the project, and this job is the one that writes
    production data

## Re-creating from scratch (if ever needed)

The commands below pre-date the dedicated accounts and still name the default
Compute Engine account. Use them for the bucket, job and scheduler resources,
then run `deploy/harden_refresh_sa.sh` to put the least-privilege accounts in
place instead of the three Compute-account IAM bindings shown here.

```bash
gcloud storage buckets create gs://vayusense-data --location=us-central1 --uniform-bucket-level-access
gcloud storage cp data/processed/*.parquet gs://vayusense-data/processed/

gcloud storage buckets add-iam-policy-binding gs://vayusense-data \
  --member="serviceAccount:663068003180-compute@developer.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud run jobs create vayusense-refresh \
  --image=gcr.io/gen-lang-client-0133314577/vayusense:latest \
  --region=us-central1 \
  --command="python" --args="-m,benchmark.refresh_incremental" \
  --set-env-vars="VAYUSENSE_DATA_BUCKET=vayusense-data,OPENAQ_API_KEY=<key>" \
  --max-retries=1 --task-timeout=900 --memory=1Gi

gcloud run jobs add-iam-policy-binding vayusense-refresh --region=us-central1 \
  --member="serviceAccount:663068003180-compute@developer.gserviceaccount.com" \
  --role="roles/run.invoker"

gcloud iam service-accounts add-iam-policy-binding \
  663068003180-compute@developer.gserviceaccount.com \
  --member="serviceAccount:service-663068003180@gcp-sa-cloudscheduler.iam.gserviceaccount.com" \
  --role="roles/iam.serviceAccountTokenCreator"

gcloud scheduler jobs create http vayusense-nightly-refresh \
  --location=us-central1 --schedule="30 22 * * *" --time-zone="Etc/UTC" \
  --uri="https://us-central1-run.googleapis.com/v2/projects/gen-lang-client-0133314577/locations/us-central1/jobs/vayusense-refresh:run" \
  --http-method=POST \
  --oauth-service-account-email="663068003180-compute@developer.gserviceaccount.com"

# and the web service needs the bucket name:
gcloud run deploy vayusense --update-env-vars="VAYUSENSE_DATA_BUCKET=vayusense-data" ...
```

## Verifying it's working

```bash
# Fire the job immediately instead of waiting for the schedule:
gcloud scheduler jobs run vayusense-nightly-refresh --location=us-central1

# Watch it run:
gcloud run jobs executions list --job=vayusense-refresh --region=us-central1 --limit=3

# Check the live site picked up any change (max date should be recent):
curl -s "https://vayusense-663068003180.us-central1.run.app/api/calendar?city=Delhi&year=2026" \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['days'][-1])"
```

## After the archive changes: refresh the forecasts and the model

The nightly job only moves the archive forward. Forecasts and the Transformer
weights are NOT touched by it, so they are refreshed by hand when the archive
changes materially (for example after `benchmark/full_repull.py` adds stations,
which also re-averages historical days):

```bash
python -m ml.freshness          # reports model cutoff and forecast coverage; exits 1 if stale
python -m ml.train_transformer  # retrain: new cutoff = latest archive date minus 45 days
python -m ml.bench              # regenerate benchmark/forecast_bench.json + data/processed/forecasts.parquet
```

`ml/freshness.py` flags the model as stale when its training cutoff is more
than 14 days behind the cutoff a retrain would use today, and flags the
forecast cache as stale when it no longer reaches the archive's last date
plus the 7-day horizon. Then upload `forecasts.parquet` to
`gs://vayusense-data/processed/` so the running service picks it up.
