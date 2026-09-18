import os

import httpx
from fastapi import FastAPI, HTTPException

from .infrai_rerank import InfraiError, InfraiRerankClient
from .models import RerankRequest, RerankResponse
from .shipment_search import rerank_shipments

app = FastAPI(title="Shipment exception reranker")


@app.post("/rerank", response_model=RerankResponse)
async def rerank_route(request: RerankRequest) -> RerankResponse:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is not configured")
    try:
        return await rerank_shipments(request, InfraiRerankClient(api_key))
    except InfraiError as error:
        caller_status = error.status_code if 400 <= error.status_code < 500 else 502
        raise HTTPException(
            status_code=caller_status,
            detail={"code": error.code, "message": str(error.detail.get("message", error.code))},
        ) from error
    except (httpx.RequestError, ValueError) as error:
        raise HTTPException(status_code=502, detail="Reranking request could not be completed") from error
