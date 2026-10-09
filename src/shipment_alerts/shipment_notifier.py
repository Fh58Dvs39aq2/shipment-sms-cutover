from typing import Protocol

from .models import AlertAccepted, ShipmentEvent, ShipmentEventType


class SmsSender(Protocol):
    def batch_send(
        self, *, messages: list[dict[str, str]], idempotency_key: str
    ) -> dict[str, object]:
        raise AssertionError("Use a concrete SMS sender")


def notify_shipment(event: ShipmentEvent, sms: SmsSender) -> AlertAccepted:
    if event.event_type is ShipmentEventType.IN_TRANSIT:
        return AlertAccepted(event_id=event.event_id, disposition="skipped_in_transit")

    if event.event_type is ShipmentEventType.DELIVERED:
        proof = event.proof_of_delivery
        if proof is None or not proof.verified:
            return AlertAccepted(
                event_id=event.event_id, disposition="skipped_unverified_proof"
            )
        body = f"Shipment {event.tracking_number} was delivered."
    else:
        summary = event.exception_summary or "Carrier review required"
        body = f"Shipment {event.tracking_number} needs attention: {summary}."

    data = sms.batch_send(
        messages=[{"to": event.recipient_phone, "body": body}],
        idempotency_key=f"shipment-event:{event.event_id}",
    )
    message_id = data.get("message_id")
    if message_id is None:
        messages = data.get("messages")
        if isinstance(messages, list) and messages and isinstance(messages[0], dict):
            message_id = messages[0].get("message_id")
    return AlertAccepted(
        event_id=event.event_id,
        disposition="sent",
        message_id=str(message_id) if message_id else None,
    )
