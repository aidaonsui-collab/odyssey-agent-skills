# Bonding Curve Math Reference

## On-chain Constants — Initial Pool State

These are the values every new pool starts with, from the live Configuration object:

```
VIRTUAL_TOKEN_INIT  = 533_333_333_500_000   # raw (6 decimals → ~533M tokens)
VIRTUAL_SUI_INIT    = 2_000_000_000_000     # raw (9 decimals → 2000 SUI = graduation threshold)
GRADUATION_THRESHOLD = 2_000_000_000_000_000 # 2000 SUI in MIST (from config)
TOKEN_DECIMALS      = 6
SUI_DECIMALS        = 9
PLATFORM_FEE_BPS    = 200   (2%)
```

> ⚠️ A live pool's virtual_sui_reserves and virtual_token_reserves shift with every trade.
> Always fetch the current pool object state for accurate price/output calculations.
> The values above are only for **new pool** price estimation.

## Price

```python
# For a live pool — fetch current reserves from chain
price_sui_per_token = virtual_sui / 1e9 / (virtual_token / 1e6)

# Starting price (new pool)
# = 2000 SUI / 533,333,334 tokens = ~0.00000375 SUI per token
```

## Tokens out (buy)

```python
def tokens_out(sui_mist: int, v_sui: int, v_token: int) -> int:
    """Raw token units out for sui_mist input (before fee deduction)."""
    return (sui_mist * v_token) // (v_sui + sui_mist)

# Human-readable — always use LIVE pool reserves, not initial values
async def estimate_buy(pool_id: str, sui_float: float) -> float:
    pool = await get_pool_state(pool_id)
    sui_mist = int(sui_float * 1e9)
    raw = tokens_out(sui_mist, pool['virtual_sui'], pool['virtual_token'])
    return raw / 1e6
```

## SUI out (sell)

```python
def sui_out(token_raw: int, v_sui: int, v_token: int) -> int:
    """Raw SUI mist out for token_raw input (before fee deduction)."""
    return (token_raw * v_sui) // (v_token + token_raw)
```

## Slippage / min_out

```python
SLIPPAGE_BPS = 200  # 2%

def min_out(expected: int, slippage_bps: int = SLIPPAGE_BPS) -> int:
    return expected * (10000 - slippage_bps) // 10000
```

## Bonding progress

```python
def progress_pct(real_sui_raised_mist: int, threshold_mist: int = 2_000_000_000_000_000) -> float:
    return real_sui_raised_mist / threshold_mist * 100
```

## Fetching live pool state

```python
async def get_pool_state(pool_id: str) -> dict:
    result = await rpc("sui_getObject", [pool_id, {"showContent": True}])
    f = result["data"]["content"]["fields"]
    real_sui = int(f["real_sui_reserves"]["fields"]["balance"])
    threshold = int(f["threshold"])
    return {
        "virtual_sui":   int(f["virtual_sui_reserves"]),
        "virtual_token": int(f["virtual_token_reserves"]),
        "real_sui":      real_sui,
        "threshold":     threshold,
        "is_completed":  f["is_completed"],
        "progress":      real_sui / threshold * 100,
    }
```
