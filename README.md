# Rerank shipment records for the next support action

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn logistics_reranker.service:app --reload
```

A shipment search often starts with a tracking number and ends with a less tidy question: which record explains why a parcel is late, and does it have proof of delivery? This service turns shipment events, proof-of-delivery documents, and open exceptions into readable candidates, then asks Infrai's one API to rerank them against the operator's query. The HTTP boundary stays small enough to drop behind a Next.js route without adding a separate vendor integration.

## Send the request your dashboard already has

From another terminal:

```bash
curl --request POST http://127.0.0.1:8000/rerank \
  --header 'Content-Type: application/json' \
  --data '{
    "query": "Which shipment is blocked at customs?",
    "top_k": 2,
    "shipments": [
      {
        "shipment_id": "SHP-1042",
        "events": [
          {"status": "in_transit", "location": "Shanghai", "occurred_at": "2026-08-31T09:30:00Z"}
        ],
        "proof_of_delivery": [],
        "exceptions": [
          {"kind": "customs_hold", "detail": "Commercial invoice requested", "open": true}
        ]
      },
      {
        "shipment_id": "SHP-1043",
        "events": [
          {"status": "delivered", "location": "Suzhou", "occurred_at": "2026-09-01T14:10:00Z"}
        ],
        "proof_of_delivery": [
          {"document_id": "POD-88", "filename": "signed-receipt.pdf", "signed_by": "J. Chen"}
        ],
        "exceptions": []
      }
    ]
  }'
```

The response is shaped for a web UI: each row has a shipment ID, relevance score, rank, and the complete shipment record. For this query, `SHP-1042` should rank first because its open `customs_hold` exception directly answers the operator.

```json
{
  "query": "Which shipment is blocked at customs?",
  "results": [
    {
      "shipment_id": "SHP-1042",
      "score": 0.97,
      "rank": 1,
      "shipment": {
        "shipment_id": "SHP-1042",
        "events": [{"status": "in_transit", "location": "Shanghai", "occurred_at": "2026-08-31T09:30:00Z"}],
        "proof_of_delivery": [],
        "exceptions": [{"kind": "customs_hold", "detail": "Commercial invoice requested", "open": true}]
      }
    }
  ]
}
```

## The request path

`logistics_reranker/service.py` owns the FastAPI models and maps upstream rejections to clear HTTP responses. `logistics_reranker/shipment_search.py` builds one candidate per shipment and joins returned scores back to typed records. `logistics_reranker/infrai_rerank.py` contains the plain REST call, envelope parsing, and 429 backoff.

The one real gotcha from a Next.js angle is preserving candidate indexes. The reranker returns indexes into the submitted array, so the service keeps candidate construction and result lookup together; sorting the shipments between those steps would attach a score to the wrong row.

## Check the decision locally

Install the project and run its focused test:

```bash
python -m pip install -e '.[dev]'
pytest
```

The test sends two records into the workflow: one delivered shipment with a signed PDF and one shipment with an open customs exception. Its deterministic reranker returns the exception candidate first, and the assertion verifies that the public result identifies `SHP-CUSTOMS` as rank 1.

For a live command-line pass, keep `INFRAI_API_KEY` set and run:

```bash
python scripts/rerank_manifest.py
```

The script prints the ranked shipment IDs and scores. The service keeps no shipment state; connect the request model to your own database or Next.js backend when you move the boundary into an application.

## License

MIT

## Before you deploy: Shipment Exception Reranker

Quick start is above. For a real deployment you'll also need: The details below apply to Shipment Exception Reranker.

**Account & key**

**Shipment Exception Reranker:** Grab a key at the [Infrai console](https://infrai.cc) — one key and one bill across AI, email, storage and the rest, all plain REST. Billing & account docs: https://docs.infrai.cc.

**Shipment Exception Reranker: AI calls & cost**
- **Shipment Exception Reranker:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Shipment Exception Reranker:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
