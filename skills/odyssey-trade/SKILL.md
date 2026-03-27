---
name: odyssey-trade
description: |
  Buy and sell tokens on Odyssey 2.0 bonding curve pools directly on-chain.
  
  Supports:
  - Buy with any SUI amount
  - Sell any token amount
  - Price/state queries (no gas)
  - Slippage protection
  - Dry-run estimation mode

  Use when: trading tokens on Odyssey, checking prices, managing positions.
license: MIT
metadata:
  version: "1.0.0"
  category: defi
invocation:
  pattern: "/odyssey-trade <buy|sell|price> --pool <POOL_ID> [options]"
  examples:
    - "/odyssey-trade price --pool 0x3ada..."
    - "/odyssey-trade buy --pool 0x3ada... --sui 10 --dry-run"
    - "/odyssey-trade sell --pool 0x3ada... --tokens 5000"
---

# Odyssey Trade Skill

Buy and sell on Odyssey 2.0 bonding curve pools — fully on-chain, no backend.

## Setup

```bash
pip install pysui httpx
export PRIVATE_KEY=suiprivk1...    # Your Sui private key (bech32 format)
export SLIPPAGE_BPS=200            # Optional: 200 = 2% slippage (default)
```

## Commands

### Check price
```bash
python trade.py price --pool 0x3ada016f66446b16361ec4a9b8f7a9ab8679bd945d9959d3e357619c44ea15d5
```

### Buy (estimate first)
```bash
# Dry run — see what you'd get
python trade.py buy --pool 0x3ada... --sui 10 --dry-run

# Execute
PRIVATE_KEY=suiprivk1... python trade.py buy --pool 0x3ada... --sui 10
```

### Sell
```bash
# Estimate
python trade.py sell --pool 0x3ada... --tokens 5000 --dry-run

# Execute  
PRIVATE_KEY=suiprivk1... python trade.py sell --pool 0x3ada... --tokens 5000
```

## Contract addresses

| Contract | Address |
|---|---|
| Package (v7) | `0xf1c7fe9b6ad3c243f794d41e87fab502883d5fc27e005d72e94fe64bbf08c69b` |
| Module | `moonbags` |

## Functions called

```
buy(pool, payment_coin, min_tokens_out)   → token_coin
sell(pool, token_coin, min_sui_out)       → sui_coin
```

Type arguments: `[<COIN_TYPE>, 0x2::sui::SUI]`

## Fee structure

- 2% on every buy and sell
- 30% → AIDA stakers
- 40% → token creator  
- 30% → platform

## Finding pool IDs

Pool IDs come from `GiftDeposited` events or from the Odyssey frontend URL:
```
https://theodyssey.fun/bondingcurve/coins/0x3ada...
                                          ^^^^^^^^ this is the pool ID
```

Or query all pools via the Sui RPC:
```python
# Get all TradedEventV2 events to find active pools
rpc("suix_queryEvents", [
    {"MoveEventType": "0xf1c7fe9b...::moonbags::TradedEventV2"},
    null, 50, false
])
```
