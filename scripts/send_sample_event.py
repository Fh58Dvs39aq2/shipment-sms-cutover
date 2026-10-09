from datetime import UTC, datetime

from shipment_alerts.infrai_sms import InfraiSmsClient
from shipment_alerts.models import ProofOfDelivery, ShipmentEvent, ShipmentEventType
from shipment_alerts.shipment_notifier import notify_shipment


event = ShipmentEvent(
    event_id="evt-demo-delivered-01",
    tracking_number="PKG-2048",
    recipient_phone="+14155550123",
    occurred_at=datetime.now(UTC),
    event_type=ShipmentEventType.DELIVERED,
    proof_of_delivery=ProofOfDelivery(
        object_key="pod/PKG-2048/receipt.jpg",
        sha256="a" * 64,
        captured_at=datetime.now(UTC),
        verified=True,
    ),
)

sms = InfraiSmsClient()
try:
    result = notify_shipment(event, sms)
finally:
    sms.close()
print(result.model_dump_json())
