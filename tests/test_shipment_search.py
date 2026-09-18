import asyncio
from typing import Any

from logistics_reranker.models import RerankRequest, ShipmentException, ShipmentRecord
from logistics_reranker.shipment_search import rerank_shipments


class DeterministicReranker:
    async def rerank(
        self, query: str, candidates: list[str], top_k: int
    ) -> list[dict[str, Any]]:
        assert "customs_hold" in candidates[1]
        return [
            {"index": 1, "relevance_score": 0.98},
            {"index": 0, "relevance_score": 0.12},
        ][:top_k]


def test_open_customs_exception_ranks_before_delivered_shipment() -> None:
    request = RerankRequest(
        query="Which shipment is blocked at customs?",
        top_k=2,
        shipments=[
            ShipmentRecord(shipment_id="SHP-DELIVERED"),
            ShipmentRecord(
                shipment_id="SHP-CUSTOMS",
                exceptions=[
                    ShipmentException(
                        kind="customs_hold", detail="Commercial invoice requested"
                    )
                ],
            ),
        ],
    )

    response = asyncio.run(rerank_shipments(request, DeterministicReranker()))

    assert [item.shipment_id for item in response.results] == [
        "SHP-CUSTOMS",
        "SHP-DELIVERED",
    ]
    assert response.results[0].rank == 1
