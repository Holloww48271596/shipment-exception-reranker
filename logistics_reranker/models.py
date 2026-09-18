from datetime import datetime

try:
    from pydantic import BaseModel, Field
except ModuleNotFoundError:  # Keep the shipment-ranking core usable without optional runtime deps.
    class BaseModel:
        def __init__(self, **values):
            for name, default in self.__class__.__dict__.items():
                if name.startswith("_") or (callable(default) and not isinstance(default, _FieldFactory)):
                    continue
                if name not in values:
                    values[name] = default() if isinstance(default, _FieldFactory) else default
            for name, value in values.items():
                setattr(self, name, value)

    class _FieldFactory:
        def __init__(self, factory):
            self.factory = factory

        def __call__(self):
            return self.factory()

    def Field(default=None, *, default_factory=None, **_constraints):
        return _FieldFactory(default_factory) if default_factory is not None else default


class ShipmentEvent(BaseModel):
    status: str
    location: str
    occurred_at: datetime


class ProofOfDelivery(BaseModel):
    document_id: str
    filename: str
    signed_by: str | None = None


class ShipmentException(BaseModel):
    kind: str
    detail: str
    open: bool = True


class ShipmentRecord(BaseModel):
    shipment_id: str
    events: list[ShipmentEvent] = Field(default_factory=list)
    proof_of_delivery: list[ProofOfDelivery] = Field(default_factory=list)
    exceptions: list[ShipmentException] = Field(default_factory=list)


class RerankRequest(BaseModel):
    query: str = Field(min_length=1)
    shipments: list[ShipmentRecord] = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100)


class RankedShipment(BaseModel):
    shipment_id: str
    score: float
    rank: int
    shipment: ShipmentRecord


class RerankResponse(BaseModel):
    query: str
    results: list[RankedShipment]
