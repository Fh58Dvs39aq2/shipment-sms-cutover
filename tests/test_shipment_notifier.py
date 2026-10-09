from datetime import UTC, datetime

from shipment_alerts.models import ProofOfDelivery, ShipmentEvent, ShipmentEventType
from shipment_alerts.shipment_notifier import notify_shipment


class RecordingSms:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def batch_send(self, **request: object) -> dict[str, object]:
        self.calls.append(request)
        return {"message_id": "sms_delivery_42"}


def delivered_event(*, verified: bool) -> ShipmentEvent:
    return ShipmentEvent(
        event_id="carrier-event-42",
        tracking_number="PKG-2048",
        recipient_phone="+14155550123",
        occurred_at=datetime(2026, 9, 29, 8, 30, tzinfo=UTC),
        event_type=ShipmentEventType.DELIVERED,
        proof_of_delivery=ProofOfDelivery(
            object_key="pod/PKG-2048/receipt.jpg",
            sha256="a" * 64,
            captured_at=datetime(2026, 9, 29, 8, 29, tzinfo=UTC),
            verified=verified,
        ),
    )


def test_delivery_waits_for_verified_proof_then_sends_minimal_text() -> None:
    sms = RecordingSms()

    held = notify_shipment(delivered_event(verified=False), sms)
    sent = notify_shipment(delivered_event(verified=True), sms)

    assert held.disposition == "skipped_unverified_proof"
    assert sent.model_dump() == {
        "event_id": "carrier-event-42",
        "disposition": "sent",
        "message_id": "sms_delivery_42",
    }
    assert sms.calls == [
        {
            "messages": [
                {"to": "+14155550123", "body": "Shipment PKG-2048 was delivered."}
            ],
            "idempotency_key": "shipment-event:carrier-event-42",
        }
    ]
    assert "receipt.jpg" not in str(sms.calls)
