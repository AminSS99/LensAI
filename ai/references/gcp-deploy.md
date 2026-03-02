# LensAI GCP Deployment

## Prerequisites

- Installed `gcloud` CLI
- GCP project with billing enabled
- Firestore database created in the target project
- Telegram bot token and DeepSeek API key available

## Set Variables

```bash
PROJECT_ID="YOUR_PROJECT_ID"
REGION="europe-west1"
RUNTIME="python311"
PROJECT_NUMBER="$(gcloud projects describe $PROJECT_ID --format='value(projectNumber)')"
COMPUTE_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
```

## Auth and APIs

```bash
gcloud auth login
gcloud config set project $PROJECT_ID
gcloud services enable \
  cloudfunctions.googleapis.com \
  cloudbuild.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com
```

## Create or Rotate Secrets

Create if missing:

```bash
gcloud secrets create TELEGRAM_BOT_TOKEN --replication-policy="automatic"
gcloud secrets create DEEPSEEK_API_KEY --replication-policy="automatic"
```

Add latest versions:

```bash
echo "YOUR_TELEGRAM_TOKEN" | gcloud secrets versions add TELEGRAM_BOT_TOKEN --data-file=-
echo "YOUR_DEEPSEEK_KEY" | gcloud secrets versions add DEEPSEEK_API_KEY --data-file=-
```

Grant function runtime access:

```bash
gcloud secrets add-iam-policy-binding TELEGRAM_BOT_TOKEN \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding DEEPSEEK_API_KEY \
  --member="serviceAccount:${COMPUTE_SA}" \
  --role="roles/secretmanager.secretAccessor"
```

## Deploy Functions

Deploy each entry point from `functions/main.py`.

### Telegram webhook

```bash
gcloud functions deploy telegram_webhook \
  --gen2 \
  --runtime=$RUNTIME \
  --region=$REGION \
  --source=functions \
  --entry-point=telegram_webhook \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_PROJECT_ID=$PROJECT_ID \
  --set-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,DEEPSEEK_API_KEY=DEEPSEEK_API_KEY:latest \
  --memory=512MB \
  --timeout=300s \
  --max-instances=6
```

### Scheduled digest

```bash
gcloud functions deploy scheduled_digest \
  --gen2 \
  --runtime=$RUNTIME \
  --region=$REGION \
  --source=functions \
  --entry-point=scheduled_digest \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_PROJECT_ID=$PROJECT_ID \
  --set-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest,DEEPSEEK_API_KEY=DEEPSEEK_API_KEY:latest \
  --memory=512MB \
  --timeout=300s
```

### Weekly trend alerts

```bash
gcloud functions deploy weekly_trend_alerts \
  --gen2 \
  --runtime=$RUNTIME \
  --region=$REGION \
  --source=functions \
  --entry-point=weekly_trend_alerts \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_PROJECT_ID=$PROJECT_ID \
  --set-secrets=TELEGRAM_BOT_TOKEN=TELEGRAM_BOT_TOKEN:latest \
  --memory=256MB \
  --timeout=120s
```

### Optional API endpoints

```bash
gcloud functions deploy fetch_news \
  --gen2 \
  --runtime=$RUNTIME \
  --region=$REGION \
  --source=functions \
  --entry-point=fetch_news \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_PROJECT_ID=$PROJECT_ID \
  --set-secrets=DEEPSEEK_API_KEY=DEEPSEEK_API_KEY:latest \
  --memory=512MB \
  --timeout=300s
```

```bash
gcloud functions deploy health \
  --gen2 \
  --runtime=$RUNTIME \
  --region=$REGION \
  --source=functions \
  --entry-point=health \
  --trigger-http \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$PROJECT_ID,FIRESTORE_PROJECT_ID=$PROJECT_ID \
  --memory=128MB \
  --timeout=30s
```

## Set Telegram Webhook

```bash
TOKEN="YOUR_TELEGRAM_TOKEN"
WEBHOOK_URL="$(gcloud functions describe telegram_webhook --region=$REGION --gen2 --format='value(serviceConfig.uri)')"
curl "https://api.telegram.org/bot${TOKEN}/setWebhook?url=${WEBHOOK_URL}"
```

Verify:

```bash
curl "https://api.telegram.org/bot${TOKEN}/getWebhookInfo"
```

## Configure Cloud Scheduler

Resolve function URLs:

```bash
SCHEDULED_URL="$(gcloud functions describe scheduled_digest --region=$REGION --gen2 --format='value(serviceConfig.uri)')"
WEEKLY_URL="$(gcloud functions describe weekly_trend_alerts --region=$REGION --gen2 --format='value(serviceConfig.uri)')"
```

Create hourly digest job:

```bash
gcloud scheduler jobs create http lensai-hourly-digest \
  --location=$REGION \
  --schedule="0 * * * *" \
  --time-zone="Asia/Baku" \
  --uri="$SCHEDULED_URL" \
  --http-method=GET
```

Create weekly trend alert job:

```bash
gcloud scheduler jobs create http lensai-weekly-trends \
  --location=$REGION \
  --schedule="0 9 * * 1" \
  --time-zone="Asia/Baku" \
  --uri="$WEEKLY_URL" \
  --http-method=GET
```

Run jobs manually:

```bash
gcloud scheduler jobs run lensai-hourly-digest --location=$REGION
gcloud scheduler jobs run lensai-weekly-trends --location=$REGION
```

## Smoke Tests

```bash
HEALTH_URL="$(gcloud functions describe health --region=$REGION --gen2 --format='value(serviceConfig.uri)')"
curl "$HEALTH_URL"
```

```bash
FETCH_URL="$(gcloud functions describe fetch_news --region=$REGION --gen2 --format='value(serviceConfig.uri)')"
curl "${FETCH_URL}?sources=all&summarize=true"
```

Read logs:

```bash
gcloud functions logs read telegram_webhook --region=$REGION --gen2 --limit=100
gcloud functions logs read scheduled_digest --region=$REGION --gen2 --limit=100
gcloud functions logs read weekly_trend_alerts --region=$REGION --gen2 --limit=100
```
