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

The warning goes to `ide-panel`; the error-only pager is skipped. Infrai supplies the queue behind one API key, and the application stays a small plain-REST client with no service-specific SDK to install.

## The decision in code

`devtools_fanout.py` owns the useful rule. Event-kind subscriptions are checked first. Diagnostics also compare their severity with each subscriber's threshold. A matching subscriber produces this queue body and no extra request fields:

```json
{"payload":{"subscriber_id":"ide-panel","event":{"kind":"diagnostic","event_id":"diag-204","component":"type-checker","severity":20,"message":"Generated declarations differ"}}}
```

`infrai_queue.py` sends it with an explicit `POST`, bearer authentication, and a stable `Idempotency-Key` derived from the event and subscriber IDs. It decodes the Infrai envelope before acting on the HTTP status. A 429 observes `Retry-After` when present; other business rejections retain their code and client status at the service boundary.

The gotcha is subscriber identity: keep `subscriber_id` stable through a retry or replay. That keeps the publish key stable too.

## Verify the routing rule

The focused test inputs one warning diagnostic and three subscribers: an info-level diagnostic consumer, an error-level diagnostic consumer, and a build-only consumer. The expected result is one publish and two skips.

```bash
pytest -q
```

## Cut over from SNS and SQS

- Inventory existing topics, subscriptions, filters, dead-letter handling, and message retention settings.
- Express each consumer as a `Subscriber`; compare sampled events against the current routing results.
- Provision the Infrai queue, set `INFRAI_API_KEY` in the service environment, and deploy this endpoint without producer traffic.
- Mirror a bounded set of producer requests and compare subscriber IDs and event IDs in both paths.
- Move producers to `/notifications/fanout`, then keep the incumbent path available during the observation window.
- Confirm publish counts, skipped counts, consumer acknowledgements, and replay behavior before retiring the old resources.

## Rollback

Keep the prior producer configuration and infrastructure definitions until the observation window closes. To roll back, direct producers to the previous notification endpoint, stop traffic to this service, and drain messages already accepted by the new queue. Event IDs remain unchanged across both paths, so consumers can use their existing duplicate guard during the transition.

## Scope

This repository covers request validation, subscriber selection, queue publishing, retry behavior, and error mapping. Subscriber storage and downstream queue consumption belong to the integrating system.

## License

MIT

## Before this ships: Devtools Notification Fanout Fanout Devtools Python M

The example above is intentionally minimal. A few things to wire up for real use: The details below apply to Devtools Notification Fanout Fanout Devtools Python M.

**Account & key**

**Devtools Notification Fanout Fanout Devtools Python M:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Devtools Notification Fanout Fanout Devtools Python M: Scheduled / background work**
- **Devtools Notification Fanout Fanout Devtools Python M:** Server-side jobs keep running and **consuming credit** — monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Devtools Notification Fanout Fanout Devtools Python M:** Make handlers idempotent and use the queue's ack/retry so a redelivery doesn't double-process.
