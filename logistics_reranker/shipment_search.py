from typing import Protocol, Any

from .models import RankedShipment, RerankRequest, RerankResponse, ShipmentRecord


class Reranker(Protocol):
    async def rerank(
        self, query: str, candidates: list[str], top_k: int
    ) -> list[dict[str, Any]]:
        """Return ranked candidate indexes and scores."""


def shipment_candidate(shipment: ShipmentRecord) -> str:
    events = "; ".join(
        f"{event.status} at {event.location} on {event.occurred_at.isoformat()}"
        for event in shipment.events
    ) or "no shipment events"
    documents = "; ".join(
        f"{document.filename}, signed by {document.signed_by or 'unknown'}"
        for document in shipment.proof_of_delivery
    ) or "no proof of delivery"
    exceptions = "; ".join(
        f"{item.kind}: {item.detail} ({'open' if item.open else 'resolved'})"
        for item in shipment.exceptions
    ) or "no exceptions"
    return (
        f"Shipment {shipment.shipment_id}. Events: {events}. "
        f"Proof of delivery: {documents}. Exceptions: {exceptions}."
    )


async def rerank_shipments(request: RerankRequest, reranker: Reranker) -> RerankResponse:
    candidates = [shipment_candidate(item) for item in request.shipments]
    raw_results = await reranker.rerank(
        request.query, candidates, min(request.top_k, len(candidates))
    )
    ranked: list[RankedShipment] = []
    seen_indexes: set[int] = set()
    for position, item in enumerate(raw_results, start=1):
        index = int(item["index"])
        if index < 0 or index >= len(request.shipments) or index in seen_indexes:
            raise ValueError("Rerank result referenced an invalid candidate index")
        seen_indexes.add(index)
        shipment = request.shipments[index]
        score = item.get("relevance_score", item.get("score"))
        if score is None:
            raise ValueError("Rerank result did not include a score")
        ranked.append(
            RankedShipment(
                shipment_id=shipment.shipment_id,
                score=float(score),
                rank=position,
                shipment=shipment,
            )
        )
    return RerankResponse(query=request.query, results=ranked)
