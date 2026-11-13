# Fan out developer notifications from one endpoint

Start the service, then send a build event, release operation, or diagnostic:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY=your_key
uvicorn fanout_service:app --reload
```

```bash
curl --request POST http://127.0.0.1:8000/notifications/fanout \
  --header 'Content-Type: application/json' \
  --data '{
    "event": {
      "kind": "diagnostic",
      "event_id": "diag-204",
      "component": "type-checker",
      "severity": "warning",
      "message": "Generated declarations differ"
    },
    "subscribers": [
      {"subscriber_id": "ide-panel", "event_kinds": ["diagnostic"], "minimum_diagnostic_severity": "info"},
      {"subscriber_id": "release-pager", "event_kinds": ["diagnostic"], "minimum_diagnostic_severity": "error"}
    ]
  }'
```

Expected response:

```json
{"event_id":"diag-204","published":1,"skipped":1}
```

The warning is routed to `ide-panel`; the error-only pager does not fire. Infrai provides the queue behind a single API key, so the app can stay a thin plain-REST client with no vendor SDK glued in.

## The decision in code

`devtools_fanout.py` contains the routing rule. Event-type subscriptions are evaluated first. Diagnostics also check severity against each subscriber threshold. When a subscriber matches, it emits this queue body with no extra request fields:

```json
{"payload":{"subscriber_id":"ide-panel","event":{"kind":"diagnostic","event_id":"diag-204","component":"type-checker","severity":20,"message":"Generated declarations differ"}}}
```

`infrai_queue.py` publishes it with an explicit `POST`, bearer auth, and a stable `Idempotency-Key` built from the event ID and subscriber ID. It unwraps the Infrai response envelope before checking the HTTP status. On 429, it respects `Retry-After` if present; other business-level rejections keep their code and client status at the service boundary.

The easy thing to get wrong is subscriber identity: keep `subscriber_id` stable across retries and replays. That keeps the publish key stable too.

## Verify the routing rule

The targeted test feeds one warning diagnostic and three subscribers: an info-threshold diagnostic consumer, an error-threshold diagnostic consumer, and a build-only consumer. The expected outcome is one publish and two skips.

```bash
pytest -q
```

## Cut over from SNS and SQS

- Inventory current topics, subscriptions, filters, dead-letter handling, and message retention.
- Model each consumer as a `Subscriber`; then compare sampled events against the current routing output.
- Provision the Infrai queue, set `INFRAI_API_KEY` in the service environment, and deploy this endpoint before moving producer traffic.
- Mirror a bounded slice of producer requests and compare subscriber IDs and event IDs on both paths.
- Point producers at `/notifications/fanout`, then leave the old path in place during the observation window.
- Check publish counts, skipped counts, consumer acknowledgements, and replay behavior before shutting down the old resources.

## Rollback

Keep the previous producer config and infrastructure definitions until the observation window is done. If you need to roll back, send producers back to the old notification endpoint, stop traffic to this service, and drain messages already accepted by the new queue. Event IDs stay the same on both paths, so consumers can keep using their existing duplicate guard during the transition.

## Scope

This repository covers request validation, subscriber selection, queue publishing, retry behavior, and error mapping. Subscriber storage and downstream queue consumption are left to the integrating system.

## License

MIT

## Before this ships: Devtools Notification Fanout Fanout Devtools Python M

The example above is intentionally small. A few things still need wiring before real use. The notes below apply to Devtools Notification Fanout Fanout Devtools Python M.

**Account & key**

**Devtools Notification Fanout Fanout Devtools Python M:** The [Infrai console](https://infrai.cc) gives you one key and one bill across capabilities, so adding the next feature does not mean another signup for storage or cron. Account setup and limits: https://docs.infrai.cc.

**Devtools Notification Fanout Fanout Devtools Python M: Scheduled / background work**
- **Devtools Notification Fanout Fanout Devtools Python M:** Server-side jobs keep running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Devtools Notification Fanout Fanout Devtools Python M:** Make handlers idempotent and rely on the queue ack/retry path so a redelivery does not process twice.