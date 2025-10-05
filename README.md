# Hello_World

My first repository.
This is Sinstrus. I am pretty new to programming. I hope to learn more soon.

## Fetching EVE Online market orders

The `scripts/fetch_structure_orders.py` helper script demonstrates how to pull
market order data from the EVE Swagger Interface (ESI). It targets a specific
structure or station—by default Jita IV - Moon 4 - Caldari Navy Assembly Plant
(also known as "Jita 4-4"). If you previously used an earlier helper named
`scripts/esi_structure_orders.py`, that filename now exists as a thin wrapper
around the same CLI so older instructions continue to work.

### Prerequisites

1. Install the required Python dependency:

   ```bash
   pip install requests
   ```

2. Obtain an ESI access token with the `esi-markets.structure_markets.v1`
   scope. You can generate one through the EVE Online SSO flow. Save the token
   as an environment variable named `ESI_ACCESS_TOKEN`.

   > Tokens expire roughly every 20 minutes. If the script starts returning
   > `401 Unauthorized`, repeat the SSO flow to obtain a fresh token before
   > trying again.

### Example usage

Fetch the first page of market orders from Jita 4-4 and pretty-print them to
standard output:

```bash
export ESI_ACCESS_TOKEN="<your access token>"
python scripts/fetch_structure_orders.py --max-pages 1 --pretty --output -
```

Write all available orders to a JSON file instead:

```bash
python scripts/fetch_structure_orders.py --output jita_orders.json
```

To query a different structure, pass the appropriate structure identifier via
`--structure-id`.

### Troubleshooting

If the helper exits with `Failed to query ESI: 401 Client Error: Unauthorized`,
it means the request reached ESI without a valid token. Export the
`ESI_ACCESS_TOKEN` environment variable (or use `--access-token`) with a freshly
generated token that includes the `esi-markets.structure_markets.v1` scope, then
re-run the command.

If you see `Error: ESI rejected the request (HTTP 400)`, the token exchange was
reused or the access token expired before the script could call the endpoint.
Return to the OAuth authorize URL, copy the new `code=` value, exchange it for a
fresh access token, and try again.
