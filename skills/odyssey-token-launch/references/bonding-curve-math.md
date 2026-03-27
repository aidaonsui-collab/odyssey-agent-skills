# Bonding Curve Math Reference

## On-chain Constants (live mainnet)

```
VIRTUAL_TOKEN_RESERVES = 2,131,961,013,243,971   (6 decimals → ~2.13T tokens)
VIRTUAL_SUI_RESERVES   = 2,001,287,378,847        (9 decimals → ~2001 SUI)
GRADUATION_THRESHOLD   = 2,000,000,000,000,000    (9 decimals → 2000 SUI)
TOKEN_DECIMALS         = 6
SUI_DECIMALS           = 9
PLATFORM_FEE_BPS       = 200   (2%)
```

## Price

```python
price_sui_per_token = virtual_sui / 1e9 / (virtual_token / 1e6)
```

## Tokens out (buy)

```python
def tokens_out(sui_mist: int, v_sui: int, v_token: int) -> int:
    """Raw token units out for sui_mist input (before fee deduction)."""
    return (sui_mist * v_token) // (v_sui + sui_mist)

# Human-readable
def tokens_out_float(sui_float: float) -> float:
    sui_mist = int(sui_float * 1e9)
    raw = tokens_out(sui_mist, VIRTUAL_SUI_RESERVES, VIRTUAL_TOKEN_RESERVES)
    return raw / 1e6
```

## SUI out (sell)

```python
def sui_out(token_raw: int, v_sui: int, v_token: int) -> int:
    """Raw SUI mist out for token_raw input (before fee deduction)."""
    return (token_raw * v_sui) // (v_token + token_raw)
```

## Slippage / min_out

Always set a minimum output to protect against MEV/front-running:

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

## Example

```python
# Buy 10 SUI worth of tokens
sui_in = 10.0
est_tokens = tokens_out_float(sui_in)
# ≈ 10,636 tokens at current reserves

# At graduation (2000 SUI raised), token migrates to Turbos DEX
# Creator gets their locked tokens, AIDA stakers earned 30% of all fees
```
