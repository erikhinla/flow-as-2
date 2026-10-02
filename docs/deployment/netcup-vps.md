# Netcup live deploy

This is the live path for the client product: the BizBuilders diagnostic, the governed intake registry, and the operator desk. It does not start the agent runtimes.

## Host

Use a Netcup VPS with Docker Engine and Docker Compose. Open these ports:

- `22` for SSH
- `8080` for the diagnostic, until HTTPS is on (`DIAGNOSTIC_PORT`)
- `5173` for the desk, until HTTPS is on (`DESK_PORT`)
- `80` and `443` once `DIAGNOSTIC_HOST` and `DESK_HOST` are set

Do not publish Postgres or Redis.

## First boot

```bash
sudo mkdir -p /opt/flow-as
sudo chown "$USER" /opt/flow-as
git clone https://github.com/erikhinla/flow-as-2.git /opt/flow-as
cd /opt/flow-as
cp deploy/live/env.example .env
```

Edit `.env`. Every secret must be at least 24 characters and must not be a placeholder from the example. Then:

```bash
bash scripts/netcup/deploy.sh
```

The script refuses to start when a secret is still a placeholder.

## Checks

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS -u "$DASHBOARD_BASIC_AUTH_USER:$DASHBOARD_BASIC_AUTH_PASSWORD" http://127.0.0.1:5173/api/health
```

Open the diagnostic, submit one real client, then open the desk and confirm that report is listed. The desk password is the basic-auth password. The API token stays on the server; the desk proxy adds it.

## HTTPS

Point two DNS A records at the VPS, then set:

```env
DIAGNOSTIC_HOST=diagnostics.example.com
DESK_HOST=desk.example.com
ACME_EMAIL=you@example.com
```

Run the deploy script again. It binds the app ports to localhost and starts Caddy for certificates. The desk link uses `https://diagnostics.example.com/diagnostic?type=bizbuilders`.

## Behind an existing host proxy

If Caddy (or another proxy) already owns ports 80 and 443 on the VPS, do not start the stack's Caddy. Set:

```env
EXTERNAL_PROXY=1
LIVE_BIND=127.0.0.1
DIAGNOSTIC_PORT=18080
DESK_PORT=5173
DIAGNOSTIC_PUBLIC_URL=https://diagnostics.example.com/diagnostic?type=bizbuilders
```

Leaving `DIAGNOSTIC_HOST` and `DESK_HOST` blank also skips the `tls` profile. Add site blocks to the host proxy:

```caddy
diagnostics.example.com {
	encode gzip
	reverse_proxy 127.0.0.1:18080
}

desk.example.com {
	encode gzip
	reverse_proxy 127.0.0.1:5173
}
```

## Telegram webhook

The gateway serves `POST /telegram/webhook` on the diagnostic host. Set `TELEGRAM_BOT_TOKEN` and a random `TELEGRAM_WEBHOOK_SECRET` in `.env`, redeploy, then register the webhook with the same secret:

```bash
curl -fsS "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
  --data-urlencode "url=https://diagnostics.example.com/telegram/webhook" \
  --data-urlencode "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

Requests without the matching `X-Telegram-Bot-Api-Secret-Token` header get 401. Accepted updates return 200, are logged by `flow-gateway`, and are appended to `telegram/updates.jsonl` in the intake volume.

## Update

```bash
cd /opt/flow-as
git pull
bash scripts/netcup/deploy.sh
```

## Stop

```bash
docker compose --env-file .env -f deploy/live/docker-compose.yml --profile tls down
```

Named volumes keep the database and the intake reports. `down -v` deletes them.
