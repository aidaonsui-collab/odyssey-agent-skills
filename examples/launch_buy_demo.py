#!/usr/bin/env python3
"""
Odyssey Agent Skills - Complete Demo

This script demonstrates:
1. Token launch with dry-run mode
2. Guarded trading with balance checks
3. Retry logic for RPC calls

Usage:
    python examples/launch_buy_demo.py --dry-run
    python examples/launch_buy_demo.py --wallet 0x_your_address
"""

import argparse
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

# Add skills to path
sys.path.insert(0, '../skills/sui-token-launch')
sys.path.insert(0, '../skills/sui-bonding-curve-trade')
sys.path.insert(0, '../skills/onlyfence-guardrails')

from sui_token_launch.launcher import OdysseyLauncher, LaunchParams
from sui_bonding_curve_trade.trader import OdysseyTrader
from onlyfence_guardrails.guardrails import OnlyFenceGuardrails

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry logic."""
    max_retries: int = 3
    base_delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 10.0


def retry_with_backoff(
    func: Callable,
    config: RetryConfig = None,
    *args, **kwargs
):
    """
    Execute function with exponential backoff retry.
    
    Args:
        func: Function to execute
        config: Retry configuration
        *args, **kwargs: Arguments to pass to function
        
    Returns:
        Result from function
        
    Raises:
        Last exception if all retries fail
    """
    config = config or RetryConfig()
    last_exception = None
    
    for attempt in range(config.max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            if attempt < config.max_retries - 1:
                delay = min(
                    config.base_delay * (config.backoff_factor ** attempt),
                    config.max_delay
                )
                logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"All {config.max_retries} attempts failed")
    
    raise last_exception


@dataclass 
class WalletBalance:
    """Simulated wallet balance for demo."""
    sui: float = 100.0  # Default 100 SUI
    tokens: dict = field(default_factory=dict)  # token_type -> amount


class OdysseyAgent:
    """
    Autonomous agent for Odyssey token launches and trades.
    
    Features:
    - Retry logic for RPC flakes
    - Balance checks before trades
    - OnlyFence guardrails
    - Dry-run mode
    - Full audit logging
    """
    
    def __init__(
        self,
        wallet_address: str,
        dry_run: bool = True,
        enable_guardrails: bool = True
    ):
        """
        Initialize the agent.
        
        Args:
            wallet_address: Sui wallet address
            dry_run: If True, simulate without executing
            enable_guardrails: If True, enforce OnlyFence limits
        """
        self.wallet_address = wallet_address
        self.dry_run = dry_run
        self.enable_guardrails = enable_guardrails
        
        # Initialize components
        self.launcher = OdysseyLauncher()
        self.trader = OdysseyTrader()
        self.guardrails = OnlyFenceGuardrails() if enable_guardrails else None
        
        # Simulated balance (in real impl, would query RPC)
        self.balance = WalletBalance(sui=100.0)
        
        # Retry config
        self.retry_config = RetryConfig()
        
        logger.info(f"Agent initialized for wallet {wallet_address}")
        logger.info(f"Dry run: {dry_run}, Guardrails: {enable_guardrails}")
    
    def check_balance(self, required_sui: float = 0, required_tokens: float = 0) -> bool:
        """
        Check if wallet has sufficient balance.
        
        Args:
            required_sui: SUI required
            required_tokens: Tokens required (format: amount)
            
        Returns:
            True if sufficient balance
        """
        if required_sui > self.balance.sui:
            logger.error(
                f"Insufficient SUI: have {self.balance.sui}, need {required_sui}"
            )
            return False
        
        logger.info(f"Balance check passed: {self.balance.sui} SUI available")
        return True
    
    def check_gas(self, required_gas: float = 0.05) -> bool:
        """
        Check if wallet has enough for gas.
        
        Args:
            required_gas: Required gas in SUI
            
        Returns:
            True if sufficient
        """
        return self.check_balance(required_sui=required_gas)
    
    def launch_token_with_guardrails(self, params: LaunchParams) -> dict:
        """
        Launch token with full safety checks.
        
        Args:
            params: Launch parameters
            
        Returns:
            Dict with result or error
        """
        logger.info(f"=== TOKEN LAUNCH: {params.ticker} ===")
        
        # Step 1: Validate params
        error = self.launcher.validate_params(params)
        if error:
            logger.error(f"Validation failed: {error}")
            return {"success": False, "error": error}
        
        # Step 2: Check balance
        total_required = params.first_buy_sui + 0.01 + 0.05  # buy + fee + gas
        if not self.check_balance(required_sui=total_required):
            return {"success": False, "error": "Insufficient SUI balance"}
        
        # Step 3: Calculate expected tokens
        tokens = self.launcher.calculate_tokens_display(params.first_buy_sui)
        logger.info(f"Expected tokens: {tokens:,.2f} {params.ticker}")
        
        # Step 4: Dry run check
        if self.dry_run:
            logger.info("[DRY RUN] Would launch token with params:")
            logger.info(f"  Name: {params.token_name}")
            logger.info(f"  Ticker: {params.ticker}")
            logger.info(f"  First buy: {params.first_buy_sui} SUI")
            logger.info(f"  Target raise: {params.target_raise_sui} SUI")
            return {
                "success": True,
                "dry_run": True,
                "expected_tokens": tokens,
                "params": str(params)
            }
        
        # Step 5: Execute with retry
        logger.info("Executing launch transaction...")
        try:
            result = retry_with_backoff(
                self.launcher.launch_token,
                self.retry_config,
                params
            )
            
            if result.success:
                logger.info(f"SUCCESS! Pool ID: {result.pool_id}")
                return {
                    "success": True,
                    "pool_id": result.pool_id,
                    "tokens_received": result.tokens_received
                }
            else:
                logger.error(f"Launch failed: {result.error}")
                return {"success": False, "error": result.error}
                
        except Exception as e:
            logger.error(f"Launch failed after retries: {e}")
            return {"success": False, "error": str(e)}
    
    def buy_token_with_guardrails(
        self,
        pool_id: str,
        token_type: str,
        sui_amount: float
    ) -> dict:
        """
        Buy tokens with full safety checks.
        
        Args:
            pool_id: Pool ID
            token_type: Token type address
            sui_amount: Amount of SUI to spend
            
        Returns:
            Dict with result or error
        """
        logger.info(f"=== BUY ORDER: {sui_amount} SUI ===")
        
        # Step 1: Validate amount
        error = self.trader.validate_buy(sui_amount)
        if error:
            logger.error(f"Validation failed: {error}")
            return {"success": False, "error": error}
        
        # Step 2: Check balance
        if not self.check_balance(required_sui=sui_amount + 0.05):  # +gas
            return {"success": False, "error": "Insufficient SUI"}
        
        # Step 3: Check guardrails
        if self.enable_guardrails and self.guardrails:
            # Assume $1 per SUI for USD estimation (simplified)
            amount_usd = sui_amount
            check = self.guardrails.check_trade(token_type, amount_usd)
            
            if not check.allowed:
                logger.warning(f"GUARDRAIL BLOCKED: {check.reason}")
                return {"success": False, "error": check.reason, "blocked": True}
            
            logger.info(f"Guardrail check passed (24h volume: ${check.current_24h_volume})")
        
        # Step 4: Calculate expected tokens
        tokens_raw, tokens_display = self.trader.calculate_buy_tokens(sui_amount)
        price = sui_amount / tokens_display if tokens_display > 0 else 0
        logger.info(f"Expected: {tokens_display:,.2f} tokens @ {price:.10f} SUI each")
        
        # Step 5: Dry run
        if self.dry_run:
            logger.info(f"[DRY RUN] Would buy {tokens_display:,.2f} tokens")
            return {
                "success": True,
                "dry_run": True,
                "tokens_received": tokens_display,
                "price_per_token": price
            }
        
        # Step 6: Execute with retry
        logger.info("Executing buy transaction...")
        try:
            result = retry_with_backoff(
                self.trader.buy,
                self.retry_config,
                pool_id, token_type, sui_amount
            )
            
            if result.success:
                logger.info(f"SUCCESS! Received {result.tokens_display:,.2f} tokens")
                
                # Log to guardrails
                if self.enable_guardrails and self.guardrails:
                    self.guardrails.log_trade(
                        token_type, sui_amount, "buy"
                    )
                
                return {
                    "success": True,
                    "tokens_received": result.tokens_display,
                    "sui_spent": result.sui_amount,
                    "digest": result.digest
                }
            else:
                logger.error(f"Buy failed: {result.error}")
                return {"success": False, "error": result.error}
                
        except Exception as e:
            logger.error(f"Buy failed after retries: {e}")
            return {"success": False, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description='Odyssey Agent Demo')
    parser.add_argument('--wallet', default='0xDemoWallet123', help='Wallet address')
    parser.add_argument('--dry-run', action='store_true', default=True, help='Dry run mode')
    parser.add_argument('--no-guardrails', action='store_true', help='Disable guardrails')
    parser.add_argument('--real', action='store_false', dest='dry_run', help='Execute for real')
    args = parser.parse_args()
    
    print("=" * 60)
    print("ODYSSEY AGENT - COMPLETE DEMO")
    print("=" * 60)
    
    # Initialize agent
    agent = OdysseyAgent(
        wallet_address=args.wallet,
        dry_run=args.dry_run,
        enable_guardrails=not args.no_guardrails
    )
    
    # Demo 1: Token Launch
    print("\n" + "=" * 60)
    print("DEMO 1: TOKEN LAUNCH")
    print("=" * 60)
    
    launch_params = LaunchParams(
        token_name="Autonomous Agent Token",
        ticker="AAGT",
        description="A token launched by an AI agent on Odyssey",
        first_buy_sui=50.0,
        migrate_to=0,  # Cetus
        target_raise_sui=5000.0,
        twitter="https://twitter.com/agent",
        telegram="https://t.me/agent",
    )
    
    launch_result = agent.launch_token_with_guardrails(launch_params)
    print(f"\nResult: {json.dumps(launch_result, indent=2)}")
    
    # Demo 2: Buy Tokens
    print("\n" + "=" * 60)
    print("DEMO 2: BUY TOKENS")
    print("=" * 60)
    
    # Simulated pool info
    demo_pool_id = "0xDemoPool123456789"
    demo_token_type = "0xDemoToken::AAGT::AAGT"
    
    buy_result = agent.buy_token_with_guardrails(
        pool_id=demo_pool_id,
        token_type=demo_token_type,
        sui_amount=10.0
    )
    print(f"\nResult: {json.dumps(buy_result, indent=2)}")
    
    # Demo 3: Guardrail Block Demo
    print("\n" + "=" * 60)
    print("DEMO 3: GUARDRAIL BLOCK (try $300 trade)")
    print("=" * 60)
    
    blocked_result = agent.buy_token_with_guardrails(
        pool_id=demo_pool_id,
        token_type=demo_token_type,
        sui_amount=300.0  # Would exceed $200 single trade limit
    )
    print(f"\nResult: {json.dumps(blocked_result, indent=2)}")
    
    print("\n" + "=" * 60)
    print("DEMO COMPLETE")
    print("=" * 60)
    
    if args.dry_run:
        print("\nNOTE: This was a dry run. Use --real to execute for real.")


if __name__ == "__main__":
    main()
