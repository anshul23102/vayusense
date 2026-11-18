#!/usr/bin/env bash
# Moves the nightly refresh off the default Compute Engine service account
# (broad, often project-wide Editor) onto two dedicated least-privilege ones:
#
#   vayusense-refresh@    runs the job; objectUser on gs://vayusense-data only
#   vayusense-scheduler@  only triggers it; run.invoker on the one job only
#
# Safe order: create + grant new, switch job and scheduler over, run the job
# once and check it succeeds, and only then (step 5, run by hand) strip the old
# default-account bindings. Review before running; needs `gcloud auth login`.
set -euo pipefail

PROJECT=gen-lang-client-0133314577
REGION=us-central1
BUCKET=vayusense-data
JOB=vayusense-refresh
SCHED=vayusense-nightly-refresh
OLD_SA=663068003180-compute@developer.gserviceaccount.com
RUN_SA="vayusense-refresh@${PROJECT}.iam.gserviceaccount.com"
TRIG_SA="vayusense-scheduler@${PROJECT}.iam.gserviceaccount.com"
SCHED_AGENT=service-663068003180@gcp-sa-cloudscheduler.iam.gserviceaccount.com

echo "== 1) create the two service accounts"
gcloud iam service-accounts describe "$RUN_SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create vayusense-refresh \
    --display-name="VayuSense nightly refresh job (runtime)"
gcloud iam service-accounts describe "$TRIG_SA" >/dev/null 2>&1 || \
  gcloud iam service-accounts create vayusense-scheduler \
    --display-name="VayuSense nightly refresh (scheduler trigger only)"

echo "== 2) grant least privilege"
# objectUser = create/read/update/delete objects, nothing on bucket settings or IAM.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:${RUN_SA}" --role="roles/storage.objectUser"
gcloud run jobs add-iam-policy-binding "$JOB" --region="$REGION" \
  --member="serviceAccount:${TRIG_SA}" --role="roles/run.invoker"
gcloud iam service-accounts add-iam-policy-binding "$TRIG_SA" \
  --member="serviceAccount:${SCHED_AGENT}" --role="roles/iam.serviceAccountTokenCreator"

echo "== 3) switch the job and the scheduler to the new accounts"
gcloud run jobs update "$JOB" --region="$REGION" --service-account="$RUN_SA"
gcloud scheduler jobs update http "$SCHED" --location="$REGION" \
  --oauth-service-account-email="$TRIG_SA"

echo "== 4) run once and confirm success BEFORE removing anything"
gcloud scheduler jobs run "$SCHED" --location="$REGION"
sleep 45
gcloud run jobs executions list --job="$JOB" --region="$REGION" --limit=1
echo "Check the latest execution above shows success, then do step 5 by hand."

cat <<EOF

== 5) AFTER a verified run: remove the old broad bindings (run by hand)
gcloud storage buckets remove-iam-policy-binding gs://${BUCKET} \\
  --member="serviceAccount:${OLD_SA}" --role="roles/storage.objectAdmin"
gcloud run jobs remove-iam-policy-binding ${JOB} --region=${REGION} \\
  --member="serviceAccount:${OLD_SA}" --role="roles/run.invoker"
gcloud iam service-accounts remove-iam-policy-binding ${OLD_SA} \\
  --member="serviceAccount:${SCHED_AGENT}" --role="roles/iam.serviceAccountTokenCreator"
EOF
