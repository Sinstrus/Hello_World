"""Utilities for querying EVE Online market orders for specific structures.

This module provides a small command line interface for downloading market
orders from the EVE Swagger Interface (ESI). The script is intentionally
minimal to make it easier to extend for future automation tasks.

Example usage (requires a valid ESI access token with the
``esi-markets.structure_markets.v1`` scope)::

    export ESI_ACCESS_TOKEN="<your access token>"
    python scripts/fetch_structure_orders.py --structure-id 60003760 \
        --max-pages 2 --output orders.json

"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Iterable, List, Mapping, Optional

import requests

ESI_BASE_URL = "https://esi.evetech.net/latest"
MARKET_STRUCTURE_PATH = "/markets/structures/{structure_id}/"
DEFAULT_STRUCTURE_ID = 60003760  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
DATASOURCE = "tranquility"


class ESIError(RuntimeError):
    """Raised when the ESI API returns an unexpected response."""


def _build_headers(access_token: Optional[str]) -> Mapping[str, str]:
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def fetch_structure_orders(
    structure_id: int,
    access_token: Optional[str] = None,
    max_pages: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> List[Mapping[str, object]]:
    """Fetch all market orders for a structure.

    Parameters
    ----------
    structure_id:
        The structure (or station) identifier whose orders should be fetched.
    access_token:
        OAuth2 access token with the ``esi-markets.structure_markets.v1`` scope.
    max_pages:
        Optional limit on the number of ESI pages to retrieve. Useful when
        testing to avoid large downloads.
    session:
        Optional ``requests.Session`` for advanced use cases.
    """

    http = session or requests.Session()
    headers = _build_headers(access_token)
    params = {"datasource": DATASOURCE}

    orders: List[Mapping[str, object]] = []
    page = 1
    total_pages = None

    while True:
        if max_pages is not None and page > max_pages:
            break

        params["page"] = page
        url = f"{ESI_BASE_URL}{MARKET_STRUCTURE_PATH}".format(structure_id=structure_id)
        response = http.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 400:
            # 400 responses usually indicate a malformed or expired token even
            # though the structure ID itself is valid. Surface the message from
            # ESI so the user knows what went wrong.
            error_detail = None
            try:
                payload = response.json()
                if isinstance(payload, Mapping):
                    error_detail = payload.get("error")
            except ValueError:
                error_detail = response.text.strip() or None

            if not error_detail:
                error_detail = "Bad request"

            raise ESIError(
                "ESI rejected the request (HTTP 400). "
                f"Details: {error_detail}. "
                "This typically happens when the authorization code has "
                "already been redeemed or the access token has expired. "
                "Generate a fresh token and retry the request."
            )

        if response.status_code == 401:
            message = [
                "ESI rejected the request as unauthorized. ",
            ]
            if not access_token:
                message.append(
                    "No access token was provided; export the ESI_ACCESS_TOKEN "
                    "environment variable or supply --access-token."
                )
            else:
                message.append(
                    "Access tokens expire quickly and must include the "
                    "'esi-markets.structure_markets.v1' scope. Generate a fresh "
                    "token through EVE SSO and try again."
                )
            raise ESIError("".join(message))

        if response.status_code == 403:
            raise ESIError(
                "Access to the structure market endpoint was denied. "
                "Confirm that your access token includes the "
                "'esi-markets.structure_markets.v1' scope and that you have "
                "permission to view this structure's market orders."
            )

        if response.status_code == 404:
            raise ESIError(
                "The requested structure was not found. Double-check the "
                "structure ID (e.g. 60003760 for Jita 4-4)."
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - defensive
            raise ESIError(f"Failed to query ESI: {exc}") from exc

        try:
            page_orders = response.json()
        except ValueError as exc:  # pragma: no cover - defensive
            raise ESIError("ESI returned malformed JSON") from exc

        if not isinstance(page_orders, list):
            raise ESIError("Unexpected ESI response shape; expected a list of orders")

        orders.extend(page_orders)

        if total_pages is None:
            total_pages_header = response.headers.get("X-Pages")
            if total_pages_header:
                try:
                    total_pages = int(total_pages_header)
                except ValueError:
                    raise ESIError("Invalid 'X-Pages' header returned by ESI")
            else:
                total_pages = 1

        if total_pages is not None and page >= total_pages:
            break

        page += 1

    return orders


def _parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--structure-id",
        type=int,
        default=DEFAULT_STRUCTURE_ID,
        help="Structure/station ID to query (default: %(default)s for Jita 4-4)",
    )
    parser.add_argument(
        "--access-token",
        default=os.environ.get("ESI_ACCESS_TOKEN"),
        help="ESI OAuth2 access token. Defaults to the ESI_ACCESS_TOKEN environment variable.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional limit on the number of pages to download. Useful for testing.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Optional path to write the fetched orders as JSON.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the output JSON (useful with --output=- for stdout).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = _parse_args(argv)

    if not args.access_token:
        print(
            "Warning: No access token provided. The structure market endpoint "
            "requires an authenticated request. Set the ESI_ACCESS_TOKEN "
            "environment variable or use --access-token.",
            file=sys.stderr,
        )

    try:
        orders = fetch_structure_orders(
            structure_id=args.structure_id,
            access_token=args.access_token,
            max_pages=args.max_pages,
        )
    except ESIError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    output_data = orders

    if args.output:
        if args.output == "-":
            dump_target = sys.stdout
        else:
            dump_target = open(args.output, "w", encoding="utf-8")
    else:
        dump_target = sys.stdout

    with dump_target:
        json.dump(output_data, dump_target, indent=2 if args.pretty else None)
        if args.pretty:
            dump_target.write("\n")

    print(f"Fetched {len(orders)} orders from structure {args.structure_id}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
