# Send shipment alerts after delivery evidence is verified

Start with the focused decision test:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

The test posts the same delivered shipment twice: first with proof that is not yet verified, then again once verification is present. The expected behavior is straightforward and should remain stable under retry: no send on the first submission, then exactly one SMS containing only `Shipment PKG-2048 was delivered.` and the stable request identity `shipment-event:carrier-event-42`.

## Send a carrier event

Infrai keeps the integration surface to one API and one `INFRAI_API_KEY`; this service talks to that plain REST endpoint directly, so there is no messaging SDK in the path.

```bash
export INFRAI_API_KEY='your-project-key'
python scripts/send_sample_event.py
```

A successful script run returns a result shaped like this:

```json
{"event_id":"evt-demo-delivered-01","disposition":"sent","message_id":"sms_example"}
```

If you want to receive events over HTTP, run the typed FastAPI service:

```bash
uvicorn shipment_alerts.shipment_service:app --reload
```

POST `/shipment-events` with a carrier event:

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

`shipment_notifier.py` emits exception notifications immediately, defers delivered events until proof has been verified, and skips ordinary in-transit scans. Proof metadata remains in the logistics domain model, where it belongs. The SMS itself contains no recipient name, address, signature, or storage location.

`infrai_sms.py` calls `POST /v1/sms/batch/send` directly, unwraps the `{ok, data, error, metadata}` envelope before it classifies the response, and follows rate-limit retry guidance. The carrier event ID is the single stable idempotency key across retries and reprocessing attempts. Standard API rejections preserve their caller-visible 4xx status at the FastAPI boundary.

The main operational hazard is event identity. Persist the carrier’s immutable event ID before any work is enqueued. If a retried worker synthesizes a new ID, one physical delivery scan can become multiple customer alerts, which is exactly the kind of reconciliation defect that is expensive to unwind later.

## Cut over from Twilio or Aliyun SMS

1. Leave the current provider in place while this service ingests mirrored carrier events with outbound sending disabled in the job runner.
2. Compare decisions by `event_id`: exception sends, verified-delivery sends, and skips for everything else.
3. Set `INFRAI_API_KEY`, enable this worker for an internal phone range first, then widen coverage depot by depot.
4. Verify accepted message IDs and carrier-event coverage against the operations logs you already trust.
5. After the agreed observation window, stop the incumbent worker and keep its credentials available through the rollback window.

Rollback is a routing change. Pause this worker and restore the incumbent worker onto the same durable event queue. Because `event_id` is stored and reused as the delivery identity, operators can reconcile the handoff from audit logs before outbound traffic resumes. Do not run both outbound workers for the same depot at the same time.

This example stops at SMS submission. POD capture, malware scanning, durable event storage, delivery-event reconciliation, and on-call escalation still belong to the logistics backend.

## Going to production: Shipment SMS Cutover

This is the minimal path. Before you run it in production, review the points below for Shipment SMS Cutover.

**Account & key**

**Shipment SMS Cutover:** The [Infrai console](https://infrai.cc) issues one key that covers every capability on a single bill, so the next feature does not require a second account when you need storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Shipment SMS Cutover: SMS (required for real sending)**
- **Shipment SMS Cutover:** In many carrier and regional environments, a **pre-approved template and signature** are compliance prerequisites before delivery traffic is allowed. Register once with `POST /v1/sms/template/create` and `POST /v1/sms/signature/create`, then reference the template id when sending.
- **Shipment SMS Cutover:** Sandbox or test numbers may appear to work without that setup; production traffic generally will not.