# Hello_World

My first repository.
This is Sinstrus. I am pretty new to programming. I hope to learn more soon.

## Fetching EVE Online market orders

The `scripts/fetch_structure_orders.py` helper script demonstrates how to pull
market order data from the EVE Swagger Interface (ESI). It can query public NPC
stations *or* authenticated Upwell structures. By default it targets Jita IV -
Moon 4 - Caldari Navy Assembly Plant (also known as "Jita 4-4"). If you
previously used an earlier helper named `scripts/esi_structure_orders.py`, that
filename now exists as a thin wrapper around the same CLI so older instructions
continue to work.

### Prerequisites

1. Install the required Python dependency:

   ```bash
   pip install requests
   ```

2. (Only for Upwell structures) Obtain an ESI access token with the
   `esi-markets.structure_markets.v1` scope through the EVE Online SSO flow and
   save it as an environment variable named `ESI_ACCESS_TOKEN`.

   > Tokens expire roughly every 20 minutes. If the script starts returning
   > `401 Unauthorized` while querying a structure, repeat the SSO flow to obtain
   > a fresh token before trying again.

### Example usage

Fetch the first page of market orders from Jita 4-4 and pretty-print them to
standard output (no access token required for NPC stations):

```bash
python scripts/fetch_structure_orders.py --max-pages 1 --pretty --output -
```

Write all available orders to a JSON file instead:

```bash
python scripts/fetch_structure_orders.py --output jita_orders.json
```

To query a different NPC station, pass `--station-id <station_id>`. To query an
Upwell structure, provide `--structure-id <structure_id>` and export
`ESI_ACCESS_TOKEN` (or pass `--access-token <token>` on the command line).

### Troubleshooting

If the helper exits with a message like `Error: ESI rejected the request. HTTP
401 Unauthorized ...`, the request reached ESI without a valid token. Export
the `ESI_ACCESS_TOKEN` environment variable (or include the token directly on
the command line with `--access-token <token>`) using a freshly generated token
that includes the `esi-markets.structure_markets.v1` scope, then re-run the
command.

If you see an error such as `Error: ESI rejected the request. HTTP 400 Bad
Request ... Invalid structure identifier`, the target ID is not compatible with
the endpoint you chose. NPC hubs like Jita 4-4 must be queried with
`--station-id`, while player-owned structures require `--structure-id` plus a
valid access token. For other `400` responses when querying structures, the
authorization code was already redeemed or the access token expired—repeat the
OAuth flow for a fresh token and retry.
