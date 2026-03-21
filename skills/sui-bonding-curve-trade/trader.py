"""
Odyssey Bonding Curve Trader

AI agent skill for buying and selling tokens on the Odyssey 2.0 bonding curve.
"""

import os
from dataclasses import dataclass
from typing import Optional, List, Tuple
import json

# Contract addresses (mainnet)
ODYSSEY_PKG = "0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da"
MODULE = "moonbags"
SUI_CLOCK = "0x0000000000000000000000000000000000000000000000000000000000000006"

# Bonding curve constants (calibrated to Moonbags)
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000  # ~0.667 SUI in mist
TOKEN_DECIMALS = 6
SUI_DECIMALS = 9

# Slippage tolerance (in basis points, 50 bps = 0.5%)
DEFAULT_SLIPPAGE_BPS = 50


@dataclass
class TradeResult:
    """Result of a trade."""
    success: bool
    sui_amount: float = 0.0
    token_amount: float = 0.0
    tokens_display: float = 0.0
    price_per_token: float = 0.0
    digest: Optional[str] = None
    error: Optional[str] = None


class OdysseyTrader:
    """
    AI agent skill for trading on Odyssey bonding curves.
    
    Usage:
        trader = OdysseyTrader()
        
        # Buy tokens
        result = trader.buy(
            pool_id="0x...",
            token_type="0x...::COIN",
            sui_amount=10.0
        )
        
        # Sell tokens
        result = trader.sell(
            pool_id="0x...",
            token_type="0x...::COIN", 
            token_amount=1000.0
        )
    """
    
    def __init__(self, rpc_url: str = "https://fullnode.mainnet.sui.io:443"):
        """
        Initialize the trader.
        
        Args:
            rpc_url: Sui RPC endpoint
        """
        self.rpc_url = rpc_url
        self._wallet = None
        self._slippage_bps = DEFAULT_SLIPPAGE_BPS
    
    def set_slippage(self, bps: int):
        """
        Set slippage tolerance.
        
        Args:
            bps: Slippage in basis points (50 = 0.5%)
        """
        self._slippage_bps = max(0, min(1000, bps))  # 0-10%
    
    def set_wallet(self, address: str, sign_fn=None):
        """
        Set wallet configuration.
        
        Args:
            address: Sui wallet address
            sign_fn: Optional signing function
        """
        self._wallet = {"address": address, "sign": sign_fn}
    
    def calculate_buy_tokens(self, sui_amount: float) -> Tuple[int, float]:
        """
        Calculate tokens received for SUI input (buy side).
        
        Args:
            sui_amount: Amount of SUI to spend
            
        Returns:
            Tuple of (raw tokens, display tokens)
        """
        sui_mist = int(sui_amount * 1e9)
        tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
        tokens_display = tokens_raw / (10 ** TOKEN_DECIMALS)
        return tokens_raw, tokens_display
    
    def calculate_sell_sui(self, token_amount: float) -> Tuple[int, float]:
        """
        Calculate SUI received for tokens (sell side).
        
        Args:
            token_amount: Amount of tokens to sell
            
        Returns:
            Tuple of (SUI in mist, SUI display amount)
        """
        tokens_raw = int(token_amount * (10 ** TOKEN_DECIMALS))
        sui_mist = (VIRTUAL_SUI_START * tokens_raw) // (VIRTUAL_TOKEN_RESERVES + tokens_raw)
        sui_display = sui_mist / 1e9
        return sui_mist, sui_display
    
    def apply_slippage(self, amount_mist: int) -> int:
        """
        Apply slippage tolerance to an amount.
        
        Args:
            amount_mist: Amount in mist
            
        Returns:
            Minimum amount after slippage
        """
        return amount_mist * (10000 - self._slippage_bps) // 10000
    
    def get_effective_price(self, sui_amount: float, tokens_display: float) -> float:
        """
        Calculate effective price per token.
        
        Args:
            sui_amount: SUI spent
            tokens_display: Tokens received
            
        Returns:
            Price per token in SUI
        """
        if tokens_display == 0:
            return 0.0
        return sui_amount / tokens_display
    
    def validate_buy(self, sui_amount: float) -> Optional[str]:
        """
        Validate buy parameters.
        
        Args:
            sui_amount: Amount of SUI to spend
            
        Returns:
            Error message if invalid
        """
        if sui_amount <= 0:
            return "SUI amount must be positive"
        if sui_amount < 0.01:
            return "Minimum buy is 0.01 SUI"
        return None
    
    def validate_sell(self, token_amount: float) -> Optional[str]:
        """
        Validate sell parameters.
        
        Args:
            token_amount: Amount of tokens to sell
            
        Returns:
            Error message if invalid
        """
        if token_amount <= 0:
            return "Token amount must be positive"
        if token_amount < 1:
            return "Minimum sell is 1 token"
        return None
    
    def build_buy_tx(
        self,
        pool_id: str,
        token_type: str,
        sui_amount: float,
        min_tokens_out: Optional[int] = None
    ) -> dict:
        """
        Build buy transaction.
        
        Args:
            pool_id: Pool ID
            token_type: Token type address
            sui_amount: Amount of SUI to spend
            min_tokens_out: Minimum tokens to receive (for slippage)
            
        Returns:
            Transaction data
        """
        sui_mist = int(sui_amount * 1e9)
        tokens_raw, tokens_display = self.calculate_buy_tokens(sui_amount)
        min_tokens = min_tokens_out or self.apply_slippage(tokens_raw)
        
        return {
            "kind": "move_call",
            "target": f"{ODYSSEY_PKG}::{MODULE}::buy",
            "type_arguments": [token_type],
            "arguments": {
                "pool": pool_id,
                "payment": str(sui_mist),
                "min_tokens_out": str(min_tokens),
                "clock": SUI_CLOCK,
            },
            "gas_budget": 50_000_000
        }
    
    def build_sell_tx(
        self,
        pool_id: str,
        token_type: str,
        token_amount: float,
        min_sui_out: Optional[int] = None
    ) -> dict:
        """
        Build sell transaction.
        
        Args:
            pool_id: Pool ID
            token_type: Token type address
            token_amount: Amount of tokens to sell
            min_sui_out: Minimum SUI to receive (for slippage)
            
        Returns:
            Transaction data
        """
        tokens_raw = int(token_amount * (10 ** TOKEN_DECIMALS))
        sui_mist, sui_display = self.calculate_sell_sui(token_amount)
        min_sui = min_sui_out or self.apply_slippage(sui_mist)
        
        return {
            "kind": "move_call", 
            "target": f"{ODYSSEY_PKG}::{MODULE}::sell",
            "type_arguments": [token_type],
            "arguments": {
                "pool": pool_id,
                "tokens": str(tokens_raw),
                "min_sui_out": str(min_sui),
                "clock": SUI_CLOCK,
            },
            "gas_budget": 50_000_000
        }
    
    def buy(
        self,
        pool_id: str,
        token_type: str,
        sui_amount: float,
        dry_run: bool = False
    ) -> TradeResult:
        """
        Buy tokens from bonding curve.
        
        Args:
            pool_id: Pool ID of the token
            token_type: Token type address
            sui_amount: Amount of SUI to spend
            dry_run: If True, simulate without executing
            
        Returns:
            TradeResult with success status and details
        """
        error = self.validate_buy(sui_amount)
        if error:
            return TradeResult(success=False, error=error)
        
        sui_mist = int(sui_amount * 1e9)
        tokens_raw, tokens_display = self.calculate_buy_tokens(sui_amount)
        price = self.get_effective_price(sui_amount, tokens_display)
        
        tx = self.build_buy_tx(pool_id, token_type, sui_amount)
        
        if dry_run:
            return TradeResult(
                success=True,
                sui_amount=sui_amount,
                token_amount=tokens_raw,
                tokens_display=tokens_display,
                price_per_token=price,
                error="(dry run)"
            )
        
        # TODO: Execute via Sui RPC
        return TradeResult(
            success=True,
            sui_amount=sui_amount,
            token_amount=tokens_raw,
            tokens_display=tokens_display,
            price_per_token=price,
            error="Execution not implemented - use with Sui SDK"
        )
    
    def sell(
        self,
        pool_id: str,
        token_type: str,
        token_amount: float,
        dry_run: bool = False
    ) -> TradeResult:
        """
        Sell tokens back to bonding curve.
        
        Args:
            pool_id: Pool ID of the token
            token_type: Token type address
            token_amount: Amount of tokens to sell
            dry_run: If True, simulate without executing
            
        Returns:
            TradeResult with success status and details
        """
        error = self.validate_sell(token_amount)
        if error:
            return TradeResult(success=False, error=error)
        
        tokens_raw = int(token_amount * (10 ** TOKEN_DECIMALS))
        sui_mist, sui_display = self.calculate_sell_sui(token_amount)
        price = self.get_effective_price(sui_display, token_amount) if token_amount > 0 else 0
        
        tx = self.build_sell_tx(pool_id, token_type, token_amount)
        
        if dry_run:
            return TradeResult(
                success=True,
                sui_amount=sui_display,
                token_amount=tokens_raw,
                tokens_display=token_amount,
                price_per_token=price,
                error="(dry run)"
            )
        
        # TODO: Execute via Sui RPC
        return TradeResult(
            success=True,
            sui_amount=sui_display,
            token_amount=tokens_raw,
            tokens_display=token_amount,
            price_per_token=price,
            error="Execution not implemented - use with Sui SDK"
        )


# Tool schemas for agent frameworks
BUY_TOOL_SCHEMA = {
    "name": "odyssey_buy_token",
    "description": "Buy tokens from Odyssey bonding curve",
    "parameters": {
        "type": "object",
        "properties": {
            "pool_id": {
                "type": "string",
                "description": "Pool ID of the token"
            },
            "token_type": {
                "type": "string",
                "description": "Token type address (e.g., 0x...::COIN::COIN)"
            },
            "sui_amount": {
                "type": "number",
                "description": "Amount of SUI to spend"
            },
            "slippage_bps": {
                "type": "integer",
                "description": "Slippage tolerance in bps (default 50 = 0.5%)"
            },
            "dry_run": {
                "type": "boolean",
                "description": "Simulate without executing"
            }
        },
        "required": ["pool_id", "token_type", "sui_amount"]
    }
}

SELL_TOOL_SCHEMA = {
    "name": "odyssey_sell_token",
    "description": "Sell tokens back to Odyssey bonding curve",
    "parameters": {
        "type": "object",
        "properties": {
            "pool_id": {
                "type": "string",
                "description": "Pool ID of the token"
            },
            "token_type": {
                "type": "string",
                "description": "Token type address"
            },
            "token_amount": {
                "type": "number",
                "description": "Amount of tokens to sell"
            },
            "slippage_bps": {
                "type": "integer", 
                "description": "Slippage tolerance in bps (default 50 = 0.5%)"
            },
            "dry_run": {
                "type": "boolean",
                "description": "Simulate without executing"
            }
        },
        "required": ["pool_id", "token_type", "token_amount"]
    }
}


if __name__ == "__main__":
    # Example usage
    trader = OdysseyTrader()
    
    # Buy example
    result = trader.buy(
        pool_id="0x1234...5678",
        token_type="0xabcd...efgh::TEST::TEST",
        sui_amount=10.0,
        dry_run=True
    )
    print(f"Buy Success: {result.success}")
    print(f"SUI spent: {result.sui_amount}")
    print(f"Tokens received: {result.tokens_display}")
    print(f"Price per token: {result.price_per_token}")
    
    # Sell example
    result = trader.sell(
        pool_id="0x1234...5678",
        token_type="0xabcd...efgh::TEST::TEST",
        token_amount=1000.0,
        dry_run=True
    )
    print(f"\nSell Success: {result.success}")
    print(f"Tokens sold: {result.tokens_display}")
    print(f"SUI received: {result.sui_amount}")
