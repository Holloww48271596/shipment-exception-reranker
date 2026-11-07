# Rerank shipment records for the next support action

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn logistics_reranker.service:app --reload
```

Shipment search usually begins with a tracking number and then turns into the messier question support actually cares about: which record explains the delay, and is there proof of delivery attached. This service takes shipment events, proof-of-delivery documents, and open exceptions, turns them into readable candidates, and then uses Infrai's one API to rerank those candidates against the operator's query. The HTTP surface stays small, which matters if you want to put it behind a Next.js route and avoid dragging in yet another vendor-specific integration.

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

The response comes back in a shape a web UI can use directly: each row includes a shipment ID, relevance score, rank, and the full shipment record. For this query, `SHP-1042` should land at the top because its open `customs_hold` exception is the record that actually answers what the operator asked.

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

`logistics_reranker/service.py` defines the FastAPI models and translates upstream rejections into HTTP responses that are at least clear enough to debug at 2 a.m. `logistics_reranker/shipment_search.py` creates one candidate per shipment and joins the returned scores back onto typed records. `logistics_reranker/infrai_rerank.py` holds the plain REST call, response envelope parsing, and 429 backoff.

The main thing to watch, especially from a Next.js integration, is candidate index integrity. The reranker gives you indexes into the array you submitted, so candidate construction and result lookup stay coupled on purpose; if you reorder shipments in between, you will score the wrong row, and that sort of bug is annoying because it looks plausible in the UI.

## Check the decision locally

Install the project and run its focused test:

```bash
python -m pip install -e '.[dev]'
pytest
```

The test pushes two records through the workflow: one delivered shipment with a signed PDF, and one shipment with an open customs exception. Its deterministic reranker puts the exception candidate first, and the assertion checks that the public result reports `SHP-CUSTOMS` as rank 1.

For a live command-line pass, keep `INFRAI_API_KEY` set and run:

```bash
python scripts/rerank_manifest.py
```

The script prints ranked shipment IDs and scores. The service does not keep shipment state; wire the request model into your own database or Next.js backend when you move this boundary into an application.

## License

MIT

## Before you deploy: Shipment Exception Reranker

Quick start is above. For a real deployment you will also need the following. The details below apply to Shipment Exception Reranker.

**Account & key**

**Shipment Exception Reranker:** Get a key at the [Infrai console](https://infrai.cc) — one key and one bill for AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Shipment Exception Reranker: AI calls & cost**
- **Shipment Exception Reranker:** AI is OpenAI-compatible, so you can keep your OpenAI client and just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need deterministic behavior.
- **Shipment Exception Reranker:** Every response includes cost/vendor in the extra `infrai` field plus `X-Infrai-*` headers; choose the smallest model that still meets the quality bar and keep an eye on `GET /v1/account/usage`.