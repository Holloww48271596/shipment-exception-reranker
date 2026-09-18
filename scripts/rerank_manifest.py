import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from logistics_reranker.infrai_rerank import InfraiRerankClient
from logistics_reranker.models import (
    ProofOfDelivery,
    RerankRequest,
    ShipmentEvent,
    ShipmentException,
    ShipmentRecord,
)
from logistics_reranker.shipment_search import rerank_shipments


async def main() -> None:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise SystemExit("Set INFRAI_API_KEY before running this script")
    now = datetime.now(timezone.utc)
    request = RerankRequest(
        query="Which shipment needs customs paperwork?",
        top_k=2,
        shipments=[
            ShipmentRecord(
                shipment_id="SHP-CUSTOMS",
                events=[ShipmentEvent(status="in_transit", location="Shanghai", occurred_at=now)],
                exceptions=[ShipmentException(kind="customs_hold", detail="Commercial invoice requested")],
            ),
            ShipmentRecord(
                shipment_id="SHP-DELIVERED",
                events=[ShipmentEvent(status="delivered", location="Suzhou", occurred_at=now)],
                proof_of_delivery=[ProofOfDelivery(document_id="POD-88", filename="signed-receipt.pdf", signed_by="J. Chen")],
            ),
        ],
    )
    response = await rerank_shipments(request, InfraiRerankClient(api_key))
    for result in response.results:
        print(f"{result.rank}. {result.shipment_id} ({result.score:.4f})")


if __name__ == "__main__":
    asyncio.run(main())
