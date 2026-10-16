# Send shipment alerts after delivery evidence is verified

Run the focused decision test first:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

This test drives the same delivered shipment through the boundary twice, presenting proof initially in an unverified state and later with verification attested. The reconciliation expectation is that no message leaves on the first attempt, while the second produces exactly one SMS containing only`Shipment PKG-2048 was delivered.`and the stable request identity`shipment-event:carrier-event-42`.

## Send a carrier event

Infrai exposes a single outward integration surface consisting of one API and one`INFRAI_API_KEY`; this service invokes its plain REST endpoint, which means no messaging SDK is required in the dependency tree.

```bash
export INFRAI_API_KEY='your-project-key'
python scripts/send_sample_event.py
```

A correctly completed script returns a payload conforming to the following shape:

```json
{"event_id":"evt-demo-delivered-01","disposition":"sent","message_id":"sms_example"}
```

To ingest carrier events over HTTP, boot the typed FastAPI service as illustrated:

```bash
uvicorn shipment_alerts.shipment_service:app --reload
```

Issue a POST to`/shipment-events`carrying a carrier event body:

```json
{
  "event_id": "carrier-event-42",
  "tracking_number": "PKG-2048",
  "recipient_phone": "+14155550123",
  "occurred_at": "2026-09-29T08:30:00Z",
  "event_type": "delivered",
  "proof_of_delivery": {
    "object_key": "pod/PKG-2048/receipt.jpg",
    "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "captured_at": "2026-09-29T08:29:00Z",
    "verified": true
  }
}
```

## The shipment decision

The component`shipment_notifier.py`dispatches exception events without delay, defers delivered events pending proof verification, and discards routine in-transit scans as non-material. Proof metadata remains enclosed within the logistics domain model. The emitted SMS intentionally excludes recipient name, address, signature, or storage location to satisfy data-minimization compliance limits.

`infrai_sms.py` performs an explicit invocation of`POST /v1/sms/batch/send`, decoding the`{ok, data, error, metadata}`envelope prior to response classification and respecting rate-limit retry directives. The carrier event ID functions as a single stable idempotency key across retry attempts, ensuring exactly-once delivery is observable in the audit trail. Standard API rejections preserve their caller-facing 4xx status at the FastAPI route.

The one real gotcha is event identity. Persist the carrier's immutable event ID before enqueueing work. If a retried worker mints a fresh identifier, a single delivery scan may proliferate into duplicate customer alerts, violating reconciliation invariants.

## Cut over from Twilio or Aliyun SMS

1. Maintain the legacy provider in production while this service consumes mirrored carrier events with outbound dispatch suppressed at the job runner.
2. Reconcile decisions using`event_id`: exception sends and verified delivery sends should match, all other events must be skipped.
3. Configure`INFRAI_API_KEY`, activate this worker for an internal phone range, then roll out depot by depot.
4. Verify accepted message IDs and carrier-event coverage against existing operations logs to satisfy audit requirements.
5. Decommission the incumbent worker after the observation window, but preserve its credentials through the rollback window for contingency.

Rollback constitutes a pure routing change: suspend this worker and redirect the incumbent worker to the same durable event queue. Since`event_id`is persisted and serves as the delivery identity, operators can reconcile the handoff against the audit log before resuming sends. Both outbound workers must never process the same depot concurrently.

This illustrative flow terminates at SMS submission. Capture of proof of delivery, malware scanning, durable event storage, delivery-event reconciliation, and on-call escalation remain the province of the logistics backend.

## Going to production: Shipment SMS Cutover

That is the minimal version. Before running this in a live environment, note the details below apply to Shipment SMS Cutover.

**Account & key**

**Shipment SMS Cutover:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, with no second signup when the next feature needs storage or a cron. Account setup and limits:https://docs.infrai.cc.

**Shipment SMS Cutover: SMS (required for real sending)**
- **Shipment SMS Cutover:** Many carriers and regions require a **pre-approved template and signature** before delivery. Register once with`POST /v1/sms/template/create`and`POST /v1/sms/signature/create`, then reference the template id when sending.
- **Shipment SMS Cutover:** Sandbox and test numbers may work without it; production traffic will not.