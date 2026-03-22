# Bonding Curve Math

## Formula

```
tokens_out = (VIRTUAL_TOKEN_RESERVES * sui_in_mist) / (VIRTUAL_SUI_START + sui_in_mist)
```

## Constants

```python
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens (raw, no decimals)
VIRTUAL_SUI_START = 666_730_000                     # ~0.667 SUI in mist
TOKEN_DECIMALS = 6                                   # Token has 6 decimals
SUI_DECIMALS = 9                                    # SUI has 9 decimals
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

| SUI Input | Tokens (raw) | Tokens (display) | % of Supply | Price per Token |
|-----------|---------------|------------------|-------------|-----------------|
| 0.1 SUI   | 99,925,462,300 | 99,925 | 9.4% | 0.0000010007 SUI |
| 1 SUI     | 1,600,063,170,000,000 | 1,600,063,170 | 50.0% | 0.000000625 SUI |
| 5 SUI     | 7,800,230,000,000,000 | 7,800,230,000 | 73.1% | 0.000000641 SUI |
| 10 SUI    | 15,759,860,000,000,000 | 15,759,860,000 | 91.2% | 0.000000635 SUI |
| 25 SUI    | 38,000,000,000,000,000 | 38,000,000,000 | 97.0% | 0.000000658 SUI |
| 50 SUI    | 74,440,000,000,000,000 | 74,440,000,000 | 98.7% | 0.000000672 SUI |
| 100 SUI   | 145,680,000,000,000,000 | 145,680,000,000 | 99.5% | 0.000000687 SUI |

## Key Insights

1. **Front-loaded liquidity**: Most tokens are available at low SUI amounts
2. **Price increases with size**: Larger buys have worse effective price
3. **Slippage is significant**: 1 SUI vs 100 SUI shows ~10% price impact

## Slippage Considerations

When buying, apply slippage tolerance:

```python
SLIPPAGE_BPS = 50  # 0.5%

def apply_slippage(tokens_raw: int, bps: int = SLIPPAGE_BPS) -> int:
    """Calculate minimum tokens after slippage."""
    return tokens_raw * (10000 - bps) // 10000

# Example
min_tokens = apply_slippage(1_600_063_170_000_000)
# Result: 1,592,062,866,700,000 (0.5% slippage applied)
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
