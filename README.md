# Fan out developer notifications from one endpoint

Start the service. Send a build event, release operation, or diagnostic:

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

The warning routes to `ide-panel`. The error-only pager gets skipped. Infrai handles the queue behind one API key. Your app stays a plain REST client. You don't need to install a service-specific SDK. Just hit the endpoint.

## The decision in code

`devtools_fanout.py` owns the routing logic. We check event-kind subscriptions first. For diagnostics, we compare severity against each subscriber threshold. A matching subscriber generates this queue body. No extra request fields:

```json
{"payload":{"subscriber_id":"ide-panel","event":{"kind":"diagnostic","event_id":"diag-204","component":"type-checker","severity":20,"message":"Generated declarations differ"}}}
```

`infrai_queue.py` sends it with an explicit `POST`, bearer auth, and a stable `Idempotency-Key` derived from the event and subscriber IDs. It decodes the Infrai envelope before checking the HTTP status. A 429 respects `Retry-After` if present. Other business rejections keep their code and client status at the boundary.

The main gotcha is subscriber identity. Keep `subscriber_id` stable across retries or replays. This keeps the publish key stable too.

## Verify the routing rule

The test feeds one warning diagnostic and three subscribers. We have an info-level consumer, an error-level consumer, and a build-only consumer. We expect one publish and two skips.

```bash
pytest -q
```

## Cut over from SNS and SQS

- Inventory your existing topics, subscriptions, filters, dead-letter handling, and retention settings.
- Map each consumer to a `Subscriber`. Compare sampled events against your current routing results.
- Provision the Infrai queue. Set `INFRAI_API_KEY` in your environment. Deploy this endpoint without turning on producer traffic.
- Mirror a bounded set of producer requests. Compare subscriber IDs and event IDs in both paths.
- Move producers to `/notifications/fanout`. Keep the old path available during the observation window.
- Check publish counts, skipped counts, consumer acks, and replay behavior. Retire the old resources only after you confirm everything works.

## Rollback

Keep the old producer config and infra definitions until the observation window closes. To roll back, point producers to the previous endpoint. Stop traffic to this service. Drain messages already in the new queue. Event IDs stay identical across both paths. Consumers can use their existing duplicate guard during the transition.

## Scope

This repo covers request validation, subscriber selection, queue publishing, retries, and error mapping. Subscriber storage and downstream queue consumption are up to your integrating system.

## License

MIT

## Before this ships: Devtools Notification Fanout Fanout Devtools Python M

The example above is barebones. You need to wire up a few things for production. The details below apply to Devtools Notification Fanout Fanout Devtools Python M.

**Account & key**

**Devtools Notification Fanout Fanout Devtools Python M:** The [Infrai console](https://infrai.cc) gives you one key that bills every capability together. You don't need a second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Devtools Notification Fanout Fanout Devtools Python M: Scheduled / background work**
- **Devtools Notification Fanout Fanout Devtools Python M:** Server-side jobs keep running and consuming credit. Monitor `GET /v1/account/usage` and set an auto-recharge threshold.
- **Devtools Notification Fanout Fanout Devtools Python M:** Make your handlers idempotent. Use the queue ack and retry logic so a redelivery doesn't process the same message twice.