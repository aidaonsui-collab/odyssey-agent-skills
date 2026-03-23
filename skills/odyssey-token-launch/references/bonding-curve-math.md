# Bonding Curve Math

## Formula

```
tokens_out = (VIRTUAL_TOKEN_RESERVES * sui_in_mist) / (VIRTUAL_SUI_START + sui_in_mist)
```

## Constants

```python
# Calibrated to Moonbags exact math:
# 1 SUI → 1,597,603.59460839 tokens
# 10 SUI → 15,763,546.79803245 tokens
# 50 SUI → 74,418,604.65117544 tokens
# 100 SUI → 139,130,434.78263023 tokens

VIRTUAL_TOKEN_RESERVES = 1_066_666_667_000_000  # raw tokens (≈ 1.0667B display tokens)
VIRTUAL_SUI_START = 666_666_666_666             # ~0.667 SUI in mist
TOKEN_DECIMALS = 6                               # Token has 6 decimals
SUI_DECIMALS = 9                               # SUI has 9 decimals
GRADUATION_THRESHOLD = 2_000_000_000_000       # 2,000 SUI (2000 * 10^9 mist)
```

## Calculations

### Buy: SUI → Tokens

```python
def calculate_buy_tokens(sui_amount: float) -> tuple[int, float]:
    """
    Calculate tokens received for SUI input.
    
    Args:
        sui_amount: Amount of SUI to spend
        
    Returns:
        Tuple of (raw_tokens, display_tokens)
    """
    sui_mist = int(sui_amount * 1e9)
    
    # Raw token calculation
    tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
    
    # Apply decimal conversion
    tokens_display = tokens_raw / (10 ** TOKEN_DECIMALS)
    
    return tokens_raw, tokens_display
```

### Sell: Tokens → SUI

```python
def calculate_sell_sui(token_amount: float) -> tuple[int, float]:
    """
    Calculate SUI received for tokens.
    
    Args:
        token_amount: Amount of tokens to sell (display amount)
        
    Returns:
        Tuple of (sui_mist, sui_display)
    """
    tokens_raw = int(token_amount * (10 ** TOKEN_DECIMALS))
    
    sui_mist = (VIRTUAL_SUI_START * tokens_raw) // (VIRTUAL_TOKEN_RESERVES + tokens_raw)
    sui_display = sui_mist / 1e9
    
    return sui_mist, sui_display
```

### Price Per Token

```python
def get_effective_price(sui_amount: float, tokens_display: float) -> float:
    """Calculate effective price per token."""
    if tokens_display == 0:
        return 0.0
    return sui_amount / tokens_display
```

## Pre-computed Values

| SUI Input | Tokens (display) | % of Supply | Price per Token |
|-----------|------------------|-------------|-----------------|
| 1 SUI     | 1,597,603.59     | 0.15%       | 0.000000626 SUI |
| 10 SUI    | 15,763,546.80    | 1.48%       | 0.000000635 SUI |
| 50 SUI    | 74,418,604.65    | 6.98%       | 0.000000672 SUI |
| 100 SUI   | 139,130,434.78   | 13.05%      | 0.000000719 SUI |
| 500 SUI   | 531,531,531.53   | 49.86%      | 0.000000941 SUI |
| 1,000 SUI | 888,888,888.89   | 83.33%      | 0.000001125 SUI |
| 2,000 SUI | 1,280,000,000.00 | 100% (graduation) | 0.000001562 SUI |

## Graduation

Tokens graduate to Cetus DEX when the bonding curve reaches 2,000 SUI in volume. At that point, the pool migrates to a concentrated liquidity AMM.

## Slippage Considerations

When buying, apply slippage tolerance:

```python
SLIPPAGE_BPS = 50  # 0.5%

def apply_slippage(tokens_raw: int, bps: int = SLIPPAGE_BPS) -> int:
    """Calculate minimum tokens after slippage."""
    return tokens_raw * (10000 - bps) // 10000

# Example
min_tokens = apply_slippage(1_597_603_594_608)
# Result: 1,589_614_576_695 (0.5% slippage applied)
```

## Volume Share (Staking Rewards)

30% of trading fees go to AIDA stakers. The fee calculation:

```python
TRADING_FEE_BPS = 200  # 2%
AIDA_STAKERS_FEE = 0.30  # 30% of fees

def calculate_staker_rewards(trade_sui_amount: float) -> float:
    """Calculate rewards going to AIDA stakers."""
    fee = trade_sui_amount * (TRADING_FEE_BPS / 10000)
    staker_share = fee * AIDA_STAKERS_FEE
    return staker_share

# Example: 10 SUI trade
# Fee: 10 * 0.02 = 0.2 SUI
# Staker rewards: 0.2 * 0.30 = 0.06 SUI
```
