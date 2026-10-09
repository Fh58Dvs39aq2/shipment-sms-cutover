from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from .infrai_sms import InfraiError, InfraiSmsClient
from .models import AlertAccepted, ShipmentEvent
from .shipment_notifier import notify_shipment


def create_app(sms: InfraiSmsClient | None = None) -> FastAPI:
    configured_sms = sms

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal configured_sms
        if configured_sms is None:
            configured_sms = InfraiSmsClient()
        app.state.sms = configured_sms
        yield
        app.state.sms.close()

    app = FastAPI(title="Shipment SMS Cutover", lifespan=lifespan)

    @app.post("/shipment-events", response_model=AlertAccepted)
    def accept_event(event: ShipmentEvent, request: Request) -> AlertAccepted:
        try:
            return notify_shipment(event, request.app.state.sms)
        except InfraiError as exc:
            status = exc.status_code if 400 <= exc.status_code < 500 else 502
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc

    return app


app = create_app()
