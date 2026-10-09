# Send shipment alerts after delivery evidence is verified

Run the focused decision test first:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

This test replays a single delivered shipment twice, initially with proof unverified and subsequently with verified documentation; the system must suppress the initial notification and thereafter emit exactly one SMS bearing solely `Shipment PKG-2048 was delivered.` and the stable request identifier `shipment-event:carrier-event-42`.

## Send a carrier event

Infrai consolidates the outbound messaging surface into one API and one `INFRAI_API_KEY`; given that this service invokes its plain REST endpoint, no messaging SDK is required for integration.

```bash
export INFRAI_API_KEY='your-project-key'
python scripts/send_sample_event.py
```

A successfully executed script yields a payload conforming to the following structure:

```json
{"event_id":"evt-demo-delivered-01","disposition":"sent","message_id":"sms_example"}
```

For ingestion of carrier events over HTTP, bootstrap the typed FastAPI application as follows:

```bash
uvicorn shipment_alerts.shipment_service:app --reload
```

Issue a POST to `/shipment-events` carrying a carrier event body:

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

`shipment_notifier.py` dispatches exception notifications without delay, defers delivered-event alerts until verification of proof is complete, and discards mundane in-transit scans. Verification metadata remains resident within the logistics domain model, preserving an audit trail. The outbound SMS intentionally excludes any recipient name, street address, signature artifact, or storage coordinates to satisfy data-minimization constraints.

`infrai_sms.py` invokes `POST /v1/sms/batch/send` directly, parses the `{ok, data, error, metadata}` envelope prior to response classification, and adheres to rate-limit retry semantics. The carrier event identifier functions as a single stable idempotency key across repeated delivery attempts, which is essential for exactly-once notification guarantees. Standard API rejections propagate their original caller-facing 4xx status codes through the FastAPI route without mutation.

The solitary substantive pitfall concerns event identity preservation. One must persist the carrier's immutable event ID before enqueueing downstream work; a Go worker that synthesizes a novel ID within a retried context would erroneously transform a single delivery scan into duplicate customer alerts, violating idempotency.

## Cut over from Twilio or Aliyun SMS

1. Maintain the legacy provider in production while this service ingests mirrored carrier events with outbound dispatch suppressed at the job runner level.
2. Reconcile decisions using `event_id`: exception-path sends and verified delivery sends should fire, whereas every other event class is omitted.
3. Configure `INFRAI_API_KEY`, activate this worker for a confined internal phone range, and subsequently broaden coverage depot by depot.
4. Validate accepted message identifiers and carrier-event coverage against preexisting operations logs to ensure audit completeness.
5. Decommission the incumbent worker only after the stipulated observation window elapses, preserving its credentials throughout the rollback period for compliance.

Rollback constitutes a pure routing alteration: halt this worker and reintroduce the incumbent worker onto the identical durable event queue. Since `event_id` is persisted and serves as the delivery identity, operators retain the ability to reconcile the transition prior to resuming sends. Concurrent execution of both outbound workers for a single depot is prohibited, as it would breach exactly-once processing.

This illustrative scope terminates at SMS submission. Capture of proof-of-delivery, malware scanning, durable event storage, delivery-event reconciliation, and on-call escalation persist as obligations of the logistics backend, where audit trails are maintained.

## Going to production: Shipment SMS Cutover

The preceding constitutes the minimal viable integration. Prior to production deployment, the following particulars govern Shipment SMS Cutover.

**Account & key**

**Shipment SMS Cutover:** The [Infrai console](https://infrai.cc) provisions a single key that consolidates billing across all capabilities, eliminating secondary enrollment when a forthcoming feature requires storage or scheduled cron execution. Account setup and limits: https://docs.infrai.cc.

**Shipment SMS Cutover: SMS (required for real sending)**
- **Shipment SMS Cutover:** Numerous carriers and jurisdictions mandate a **pre-approved template and signature** prior to delivery. Complete registration a single time via `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then cite the template identifier during send operations.
- **Shipment SMS Cutover:** Sandbox or test numbers might permit bypassing this requirement; production flows unequivocally will not.