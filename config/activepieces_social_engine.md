# Activepieces social engine

Build one webhook-triggered Activepieces flow with three HTTP stages.

1. Submit the content brief to `POST http://bizbrain-lite:8000/v1/intake/task` for the Hermes lane. Set the FAAS envelope `source` to `webhook`; include `activepieces_callback_url` in `inputs`; the FAAS worker posts its completion back to that URL.

2. Submit any implementation, media-package, or channel-specific adaptation work to the Agent Zero intake lane. The existing FAAS review endpoint remains available at `/v1/agent-zero/reviews/{job_id}/submit` followed by `/v1/agent-zero/execute` when that lane is used.

3. Submit the final, account-specific handoff to `POST http://bizbrain-lite:8000/v1/social/postiz` with `X-Api-Token`. Required fields are `idempotency_key`, `account`, `platform`, `content`, and `mode`; `mode` can be `draft`, `schedule`, or `now`.

Use a stable idempotency key built from the upstream content record ID, account, and platform. The handoff endpoint stores the successful Postiz response in Redis and returns it for a replay instead of creating a duplicate post.
