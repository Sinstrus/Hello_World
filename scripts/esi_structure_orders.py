"""Utilities for querying EVE Online market orders via the ESI API.

This module focuses on structure market order queries because the structure
endpoint is what you need to query an individual citadel, station, or Upwell
structure such as "Jita 4-4 Caldari Navy Assembly Plant" (structure ID
60003760).

The endpoint requires authentication for the vast majority of structures. If
you are querying a player owned structure you must provide an OAuth access
token that has the ``esi-markets.structure_markets.v1`` scope. For public NPC
stations (including Jita 4-4) the endpoint can be queried without
authentication, but you may still pass a token if you have one available.

Example usage from the command line::

    python scripts/esi_structure_orders.py --structure-id 60003760 --type sell

"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable, List, Optional

import requests

ESI_BASE_URL = "https://esi.evetech.net/latest"


class ESIError(RuntimeError):
    """Error raised when the ESI API returns a non-success response."""


def _headers(access_token: Optional[str] = None) -> dict:
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def fetch_structure_orders(
    structure_id: int,
    *,
    access_token: Optional[str] = None,
    order_type: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> List[dict]:
    """Fetch every page of orders for a single structure.

    Parameters
    ----------
    structure_id:
        The structure ID to query (e.g. 60003760 for Jita 4-4).
    access_token:
        Optional ESI access token. Required for player owned structures.
    order_type:
        Optionally filter orders down to ``buy`` or ``sell``. ``None`` returns
        both.
    session:
        Optional :class:`requests.Session` to reuse TCP connections during the
        paginated fetch.

    Returns
    -------
    list of dict
        Every order returned by ESI. Each entry matches the shape documented at
        https://esi.evetech.net/ui/#/Market/get_markets_structures_structure_id
    """

    if order_type and order_type not in {"buy", "sell"}:
        raise ValueError("order_type must be either 'buy', 'sell', or None")

    page = 1
    orders: List[dict] = []
    session_obj = session or requests.Session()

    try:
        while True:
            params = {"page": page}
            if order_type:
                params["order_type"] = order_type

            response = session_obj.get(
                f"{ESI_BASE_URL}/markets/structures/{structure_id}/",
                headers=_headers(access_token),
                params=params,
                timeout=30,
            )
            if response.status_code != 200:
                raise ESIError(
                    f"ESI request failed with status {response.status_code}: {response.text}"
                )

            batch = response.json()
            if not isinstance(batch, list):
                raise ESIError(
                    "Unexpected response format from ESI: expected a list of orders"
                )

            orders.extend(batch)

            total_pages = int(response.headers.get("X-Pages", "1"))
            if page >= total_pages:
                break
            page += 1

        return orders
    finally:
        if session is None:
            session_obj.close()


def iter_pretty_orders(orders: Iterable[dict]) -> Iterable[str]:
    """Yield human readable descriptions of orders."""

    for order in orders:
        location = order.get("location_id", "<unknown location>")
        order_type = "Buy" if order.get("is_buy_order") else "Sell"
        type_id = order.get("type_id")
        price = order.get("price")
        volume_remain = order.get("volume_remain")
        volume_total = order.get("volume_total")
        yield (
            f"{order_type} order for type_id {type_id} at location {location}: "
            f"price={price}, remaining={volume_remain}/{volume_total}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Query EVE Online structure market orders via ESI."
    )
    parser.add_argument(
        "--structure-id",
        type=int,
        default=60003760,
        help="The structure ID to query. Defaults to Jita 4-4 (60003760).",
    )
    parser.add_argument(
        "--access-token",
        dest="access_token",
        default=None,
        help=(
            "Optional OAuth access token with the "
            "esi-markets.structure_markets.v1 scope."
        ),
    )
    parser.add_argument(
        "--type",
        dest="order_type",
        choices=["buy", "sell"],
        help="Restrict to only buy or sell orders.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Limit how many orders to print for quick inspection.",
    )

    args = parser.parse_args(argv)

    try:
        orders = fetch_structure_orders(
            args.structure_id,
            access_token=args.access_token,
            order_type=args.order_type,
        )
    except ESIError as exc:  # pragma: no cover - CLI error handling
        print(f"Failed to fetch orders: {exc}", file=sys.stderr)
        return 1

    print(
        f"Fetched {len(orders)} orders for structure {args.structure_id}."
        " Showing the first few entries:"
    )
    for line in list(iter_pretty_orders(orders))[: args.limit]:
        print(line)

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
