from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


ORDER_SUBMISSIONS_TABLE_DOC = """
Required persistence table:

CREATE TABLE order_submissions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idempotency_key TEXT NOT NULL UNIQUE,
    market_id TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity NUMERIC(18,8) NOT NULL,
    price NUMERIC(8,6) NOT NULL,
    status TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


@dataclass(frozen=True)
class OrderRequest:
    market_id: str
    side: str
    quantity: Decimal
    price: Decimal
    portfolio_run_id: str


def generate_order_idempotency_key(request: OrderRequest) -> str:
    """Create a deterministic order key suitable for at-least-once submit loops."""

    payload = {
        "market_id": request.market_id,
        "side": request.side,
        "quantity": str(request.quantity),
        "price": str(request.price),
        "portfolio_run_id": request.portfolio_run_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class KalshiOrderClient:
    """Safe order-routing scaffold.

    This client deliberately does not submit real orders. The production
    implementation must persist each request by idempotency key before making an
    authenticated Kalshi API call, then update the stored status from the API
    response.
    """

    async def submit_order_preview(self, request: OrderRequest, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        idempotency_key = generate_order_idempotency_key(request)
        return {
            "idempotency_key": idempotency_key,
            "market_id": request.market_id,
            "side": request.side,
            "quantity": str(request.quantity),
            "price": str(request.price),
            "status": "preview_only_not_submitted",
            "metadata": metadata or {},
        }
