from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ShipmentEventType(StrEnum):
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    EXCEPTION = "exception"


class ProofOfDelivery(BaseModel):
    object_key: str = Field(min_length=1, max_length=240)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime
    verified: bool


class ShipmentEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=120)
    tracking_number: str = Field(min_length=4, max_length=60)
    recipient_phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    occurred_at: datetime
    event_type: ShipmentEventType
    exception_summary: str | None = Field(default=None, min_length=1, max_length=120)
    proof_of_delivery: ProofOfDelivery | None = None


class AlertAccepted(BaseModel):
    event_id: str
    disposition: Literal["sent", "skipped_in_transit", "skipped_unverified_proof"]
    message_id: str | None = None


EventRequest = Annotated[ShipmentEvent, Field(description="A carrier shipment event")]
