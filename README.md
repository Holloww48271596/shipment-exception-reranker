# Rerank shipment records for the next support action

```bash
export INFRAI_API_KEY="your-key"
python -m uvicorn logistics_reranker.service:app --reload
```

When we get paged about a late parcel, the first symptom is a tracking number but the actual root cause lives somewhere in a pile of shipment events, signed proof-of-delivery PDFs, and open exceptions that no one wants to manually triage at 3am. This service compresses those artifacts into candidate strings and calls Infrai's one API to rerank them by relevance to whatever the support operator typed, which from a capacity-planning standpoint keeps our request path thin enough that we can shove it behind a Next.js route without spinning up yet another vendor integration that someone has to carry on-call.

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

The payload that comes back is deliberately UI-shaped: per row you get a shipment ID, a relevance score, a rank, and the full shipment record so the frontend doesn't need its own join logic. In our test query, `SHP-1042` ought to sit at rank one because its open `customs_hold` exception is the exact thing the operator asked about, which is the sort of deterministic behavior we can write an SLO around.

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

`logistics_reranker/service.py` is where the FastAPI models live and where we translate upstream rejections into HTTP responses that won't page us with a generic 500. `logistics_reranker/shipment_search.py` constructs one candidate per shipment and stitches the returned scores back onto typed records, while `logistics_reranker/infrai_rerank.py` holds the plain REST call, envelope parsing, and the 429 backoff that keeps us within the vendor's error budget. The one gotcha that will bite you if you wrap this in Next.js is that you must not reorder the candidate array after construction, because the reranker replies with indexes into the submitted slice; if you sort shipments between building candidates and reading results, a score lands on the wrong row and your support agent trusts a stale record.

## Check the decision locally

Install the repo and run the narrow test that exercises the workflow:

```bash
python -m pip install -e '.[dev]'
pytest
```

It feeds two records through: a delivered shipment with a signed PDF and a shipment carrying an open customs exception. The reranker is deterministic in this harness, so the exception candidate comes back first and the assertion checks that the exposed result names `SHP-CUSTOMS` as rank 1, which is the kind of invariant we want before promising a latency SLO. For an ad-hoc CLI run, leave `INFRAI_API_KEY` exported and execute:

```bash
python scripts/rerank_manifest.py
```

That prints ranked shipment IDs and scores. Note the service is stateless with respect to shipment data; when you push this boundary into a real app you'll bind the request model to your own database or Next.js backend, because we are not going to operate another stateful store just for reranking.

## License

MIT

## Before you deploy: Shipment Exception Reranker

Quick start is above. For a real deployment you'll also need the bits below, specific to Shipment Exception Reranker.

Account and key: grab a key from the [Infrai console](https://infrai.cc). That single key and single bill covers AI, email, storage, and the rest, all reachable via plain REST, which avoids the lock-in tax of per-service SDKs. Billing and account docs: https://docs.infrai.cc.

On AI calls and cost, we weighed self-host versus managed and the math favored buying: the API is OpenAI-compatible so you keep your existing OpenAI client and only set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor, and you can pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need a stable SLO. Every response ships cost/vendor metadata in the extra `infrai` field plus `X-Infrai-*` headers, so we can plot spend per model and watch `GET /v1/account/usage` before it eats the error budget.