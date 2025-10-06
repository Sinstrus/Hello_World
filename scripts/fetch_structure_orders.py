"""Utilities for querying EVE Online market orders for structures or stations.

This module provides a small command line interface for downloading market
orders from the EVE Swagger Interface (ESI). The script is intentionally
minimal to make it easier to extend for future automation tasks.

Example usages::

    # Fetch the first page of orders from the public NPC station in Jita 4-4
    python scripts/fetch_structure_orders.py --max-pages 1 --pretty --output -

    # Query an Upwell structure (requires a token with the
    # ``esi-markets.structure_markets.v1`` scope)
    export ESI_ACCESS_TOKEN="<your access token>"
    python scripts/fetch_structure_orders.py --structure-id 1020998381992 \
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
MARKET_STATION_PATH = "/markets/stations/{station_id}/"
DEFAULT_STRUCTURE_ID = None
DEFAULT_STATION_ID = 60003760  # Jita IV - Moon 4 - Caldari Navy Assembly Plant
DATASOURCE = "tranquility"


class ESIError(RuntimeError):
    """Raised when the ESI API returns an unexpected response."""


def _build_headers(access_token: Optional[str]) -> Mapping[str, str]:
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    return headers


def _extract_error_details(response: Optional[requests.Response]) -> str:
    """Return a human-friendly description of an error response."""

    if response is None:
        return "No response payload was returned by requests"

    request_id = response.headers.get("X-Esi-Request-Id")

    detail: Optional[str] = None
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, Mapping):
        maybe_error = payload.get("error")
        if isinstance(maybe_error, str) and maybe_error.strip():
            detail = maybe_error.strip()
        elif payload:
            detail = json.dumps(payload, ensure_ascii=False)
    else:
        text = response.text.strip()
        if text:
            detail = text

    pieces = [
        f"HTTP {response.status_code} {response.reason}",
    ]

    if request_id:
        pieces.append(f"request-id={request_id}")

    if detail:
        pieces.append(f"details={detail}")

    return "; ".join(pieces)


def fetch_structure_orders(
    structure_id: Optional[int] = None,
    *,
    station_id: Optional[int] = None,
    access_token: Optional[str] = None,
    max_pages: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> List[Mapping[str, object]]:
    """Fetch all market orders for a structure or NPC station.

    Parameters
    ----------
    structure_id:
        The Upwell structure identifier whose orders should be fetched. Requires
        an OAuth2 token with the ``esi-markets.structure_markets.v1`` scope.
    station_id:
        Identifier of an NPC station to query. NPC station requests are public
        and ignore ``access_token``.
    access_token:
        OAuth2 access token with the ``esi-markets.structure_markets.v1`` scope.
        Required for structure queries; ignored for NPC station requests.
    max_pages:
        Optional limit on the number of ESI pages to retrieve. Useful when
        testing to avoid large downloads.
    session:
        Optional ``requests.Session`` for advanced use cases.
    """

    if (structure_id is None) == (station_id is None):
        raise ValueError("Exactly one of structure_id or station_id must be provided")

    http = session or requests.Session()
    params = {"datasource": DATASOURCE}

    if structure_id is not None:
        endpoint_path = MARKET_STRUCTURE_PATH.format(structure_id=structure_id)
        headers = _build_headers(access_token)
        endpoint_label = "structure"
    else:
        endpoint_path = MARKET_STATION_PATH.format(station_id=station_id)
        headers = _build_headers(None)
        endpoint_label = "station"

    orders: List[Mapping[str, object]] = []
    page = 1
    total_pages = None

    while True:
        if max_pages is not None and page > max_pages:
            break

        params["page"] = page
        url = f"{ESI_BASE_URL}{endpoint_path}"
        response = http.get(url, params=params, headers=headers, timeout=30)

        if response.status_code == 400:
            message = ["ESI rejected the request. ", _extract_error_details(response)]

            try:
                payload = response.json()
            except ValueError:
                payload = None

            if (
                isinstance(payload, Mapping)
                and isinstance(payload.get("error"), str)
                and "invalid structure identifier" in payload["error"].lower()
            ):
                message.append(
                    "; NPC stations such as Jita 4-4 cannot be queried via "
                    "/markets/structures/. Use --station-id (which defaults to "
                    "Jita 4-4) for NPC hubs, or supply an Upwell structure ID "
                    "that you can access if you intend to query a player-owned "
                    "structure."
                )
            else:
                message.append(
                    "; if you were targeting an authenticated structure ensure "
                    "the token is fresh and scoped to "
                    "'esi-markets.structure_markets.v1'."
                )

            raise ESIError("".join(message))

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
                "The requested {target} was not found. Double-check the "
                "identifier (e.g. 60003760 for Jita 4-4 using --station-id).".format(
                    target=endpoint_label
                )
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - defensive
            raise ESIError(
                "Failed to query ESI: "
                f"{_extract_error_details(exc.response)}"
            ) from exc

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
        help="Upwell structure ID to query (requires esi-markets.structure_markets.v1)",
    )
    parser.add_argument(
        "--station-id",
        type=int,
        default=None,
        help="NPC station ID to query. Defaults to Jita 4-4 when neither option is supplied.",
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

    if args.structure_id is not None and args.station_id is not None:
        print(
            "Error: Specify only one of --structure-id or --station-id.",
            file=sys.stderr,
        )
        return 2

    structure_id = args.structure_id
    station_id = args.station_id
    env_token = os.environ.get("ESI_ACCESS_TOKEN")

    if structure_id is None and station_id is None:
        station_id = DEFAULT_STATION_ID

    if structure_id is not None and not args.access_token:
        print(
            "Warning: No access token provided. The structure market endpoint "
            "requires an authenticated request. Set the ESI_ACCESS_TOKEN "
            "environment variable or use --access-token.",
            file=sys.stderr,
        )
    elif (
        structure_id is None
        and station_id is not None
        and args.access_token
        and args.access_token != env_token
    ):
        print(
            "Note: --access-token is ignored for NPC station queries; the "
            "endpoint is public.",
            file=sys.stderr,
        )

    try:
        orders = fetch_structure_orders(
            structure_id=structure_id,
            station_id=station_id,
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

    if structure_id is not None:
        target_desc = f"structure {structure_id}"
    else:
        target_desc = f"station {station_id}"

    print(f"Fetched {len(orders)} orders from {target_desc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
