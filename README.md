# Hello_World
My first repository.

This is Sinstrus. I am pretty new to programming. I hope to learn more soon.

## ESI Market Order Scripts

The repository now contains a small helper script that can be used to pull
market orders for a specific structure via the EVE Swagger Interface (ESI).

```
python scripts/esi_structure_orders.py --structure-id 60003760 --type sell
```

The example above fetches the sell orders listed in the Jita 4-4 Caldari Navy
Assembly Plant (structure ID ``60003760``). If you need to query a player-owned
structure you will have to provide an OAuth access token that grants the
``esi-markets.structure_markets.v1`` scope. Pass the token with the
``--access-token`` flag when running the script.

Install the dependencies with:

```
pip install -r requirements.txt
```
