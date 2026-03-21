# sui-bonding-curve-trade

Autonomous AI agent skill for buying and selling tokens on the Odyssey 2.0 bonding curve.

## Installation

```bash
pip install pysui
```

## Python Implementation

```python
from pysui import SuiClient, SuiConfig
from pysui.sui_txn import Transaction

# Configuration
ODYSSEY_PKG = "0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da"
MODULE = "moonbags"
SUI_CLOCK = "0x0000000000000000000000000000000000000000000000000000000000000006"

# Bonding curve constants (calibrated to Moonbags)
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000  # ~0.667 SUI in mist
TOKEN_DECIMALS = 6
SLIPPAGE_BPS = 50  # 0.5% slippage tolerance

class OdysseyTrader:
    def __init__(self, config_path: str = None):
        """Initialize Sui client."""
        if config_path:
            self.client = SuiClient(SuiConfig.from_yaml(config_path))
        else:
            self.client = SuiClient(SuiConfig.default())
        self.address = self.client.current_account.address
    
    def calculate_buy_tokens(self, sui_amount: float) -> int:
        """Calculate tokens received for SUI input (buy side)."""
        sui_mist = int(sui_amount * 1e9)
        tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
        return tokens_raw
    
    def calculate_sell_sui(self, token_amount: float) -> int:
        """Calculate SUI received for token input (sell side)."""
        tokens_raw = int(token_amount * (10 ** TOKEN_DECIMALS))
        sui_mist = (VIRTUAL_SUI_START * tokens_raw) // (VIRTUAL_TOKEN_RESERVES + tokens_raw)
        return sui_mist
    
    def apply_slippage(self, amount_mist: int, bps: int = SLIPPAGE_BPS) -> int:
        """Apply slippage tolerance."""
        return amount_mist * (10000 - bps) // 10000
    
    def get_token_balance(self, token_type: str) -> float:
        """Get user's token balance."""
        coins = self.client.get_coins(
            owner=self.address,
            coin_type=token_type
        ).data
        total = sum(int(c.balance) for c in coins)
        return total / (10 ** TOKEN_DECIMALS)
    
    def get_sui_balance(self) -> float:
        """Get user's SUI balance."""
        coins = self.client.get_coins(
            owner=self.address,
            coin_type="0x2::sui::SUI"
        ).data
        total = sum(int(c.balance) for c in coins)
        return total / 1e9
    
    def buy_token(
        self,
        pool_id: str,
        token_type: str,
        sui_amount: float,
        min_tokens_out: float = None
    ) -> dict:
        """Buy tokens from bonding curve."""
        sui_mist = int(sui_amount * 1e9)
        
        # Calculate expected tokens with slippage
        expected_tokens = self.calculate_buy_tokens(sui_amount)
        min_tokens = min_tokens_out * (10 ** TOKEN_DECIMALS) if min_tokens_out else self.apply_slippage(expected_tokens)
        
        tx = Transaction()
        
        # Split payment coin
        payment = tx.split_coin(tx.gas(), [sui_mist])
        
        # Execute buy
        tx.move_call(
            target=f"{ODYSSEY_PKG}::{MODULE}::buy",
            type_arguments=[token_type],
            arguments=[
                pool_id,
                payment,
                min_tokens,
                SUI_CLOCK
            ]
        )
        
        result = tx.execute(self.client)
        
        if result.effects.status.status != "success":
            raise ValueError(f"Buy failed: {result.effects.status.error}")
        
        # Extract received tokens
        tokens_received = 0
        for obj in result.created:
            if obj.owner == self.address:
                tokens_received = int(obj.balance)
        
        return {
            "success": True,
            "sui_spent": sui_amount,
            "tokens_received": tokens_received / (10 ** TOKEN_DECIMALS),
            "digest": result.digest
        }
    
    def sell_token(
        self,
        pool_id: str,
        token_type: str,
        token_amount: float,
        min_sui_out: float = None
    ) -> dict:
        """Sell tokens back to bonding curve."""
        tokens_raw = int(token_amount * (10 ** TOKEN_DECIMALS))
        
        # Calculate expected SUI with slippage
        expected_sui = self.calculate_sell_sui(token_amount)
        min_sui = min_sui_out * 1e9 if min_sui_out else self.apply_slippage(expected_sui)
        
        # Get user's token coins
        coins = self.client.get_coins(
            owner=self.address,
            coin_type=token_type
        ).data
        
        if not coins:
            raise ValueError("No tokens to sell")
        
        # Merge coins if multiple
        primary = coins[0].coin_object_id
        if len(coins) > 1:
            tx = Transaction()
            tx.merge_coins(primary, [c.coin_object_id for c in coins[1:]])
            tx.execute(self.client)
        
        # Execute sell
        tx = Transaction()
        token_coin = tx.object(primary)
        
        tx.move_call(
            target=f"{ODYSSEY_PKG}::{MODULE}::sell",
            type_arguments=[token_type],
            arguments=[
                pool_id,
                token_coin,
                min_sui,
                SUI_CLOCK
            ]
        )
        
        result = tx.execute(self.client)
        
        if result.effects.status.status != "success":
            raise ValueError(f"Sell failed: {result.effects.status.error}")
        
        # Extract received SUI
        sui_received = 0
        for obj in result.created:
            if obj.owner == self.address:
                sui_received = int(obj.balance)
        
        return {
            "success": True,
            "tokens_sold": token_amount,
            "sui_received": sui_received / 1e9,
            "digest": result.digest
        }

# Usage Example
if __name__ == "__main__":
    trader = OdysseyTrader()
    
    # Check balances
    print(f"SUI Balance: {trader.get_sui_balance()}")
    
    # Buy tokens
    result = trader.buy_token(
        pool_id="<pool_id>",
        token_type="0x...::coin_template::COIN_TEMPLATE",
        sui_amount=10.0
    )
    print(f"Bought: {result['tokens_received']} tokens")
    
    # Sell tokens
    result = trader.sell_token(
        pool_id="<pool_id>", 
        token_type="0x...::coin_template::COIN_TEMPLATE",
        token_amount=100.0
    )
    print(f"Sold: {result['sui_received']} SUI")
```

## Tool Schemas (for Agent Frameworks)

```json
{
  "name": "odyssey_buy_token",
  "description": "Buy tokens from Odyssey bonding curve",
  "parameters": {
    "type": "object",
    "properties": {
      "pool_id": {"type": "string", "description": "Pool ID of the token"},
      "token_type": {"type": "string", "description": "Token type address"},
      "sui_amount": {"type": "number", "description": "Amount of SUI to spend"},
      "min_tokens_out": {"type": "number", "description": "Minimum tokens to receive (optional, for slippage)"}
    },
    "required": ["pool_id", "token_type", "sui_amount"]
  }
}

{
  "name": "odyssey_sell_token", 
  "description": "Sell tokens back to Odyssey bonding curve",
  "parameters": {
    "type": "object",
    "properties": {
      "pool_id": {"type": "string", "description": "Pool ID of the token"},
      "token_type": {"type": "string", "description": "Token type address"},
      "token_amount": {"type": "number", "description": "Amount of tokens to sell"},
      "min_sui_out": {"type": "number", "description": "Minimum SUI to receive (optional, for slippage)"}
    },
    "required": ["pool_id", "token_type", "token_amount"]
  }
}

{
  "name": "odyssey_get_balance",
  "description": "Get wallet balances for SUI and token",
  "parameters": {
    "type": "object",
    "properties": {
      "token_type": {"type": "string", "description": "Token type address (optional, omit for SUI only)"}
    }
  }
}
```

## Bonding Curve Formula

```python
# Buy: SUI → Tokens
# tokens = (VIRTUAL_TOKEN_RESERVES * sui_in) / (VIRTUAL_SUI_START + sui_in)
# tokens_raw = (1_066_708_773_000_000_000 * sui_mist) / (666_730_000 + sui_mist)

# Sell: Tokens → SUI  
# sui_out = (VIRTUAL_SUI_START * tokens_in) / (VIRTUAL_TOKEN_RESERVES + tokens_in)
# sui_mist = (666_730_000 * tokens_raw) / (1_066_708_773_000_000_000 + tokens_raw)

# Example calculations:
# 1 SUI → ~1.6M tokens (50% of supply)
# 10 SUI → ~15.76M tokens (91% of supply)  
# 50 SUI → ~74.4M tokens (98% of supply)
```

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Insufficient balance | Not enough SUI/tokens | Reduce amount or top up |
| Pool not found | Invalid pool_id | Verify pool exists |
| Coin not found | No tokens in wallet | Check balance |
| Tx failed | Contract error | Check params, retry |
