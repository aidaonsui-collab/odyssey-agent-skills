#!/usr/bin/env python3
"""
Example: Launch a token and make first buy on Odyssey

This script demonstrates:
1. Setting up wallet connection
2. Launching a new token
3. Calculating the first buy amount
4. Building the transactions (dry-run mode)

Usage:
    python examples/launch_and_first_buy.py
"""

import os
import sys

# Add skills to path
sys.path.insert(0, '../skills/sui-token-launch')
sys.path.insert(0, '../skills/sui-bonding-curve-trade')

from sui_token_launch.launcher import OdysseyLauncher, LaunchParams
from sui_bonding_curve_trade.trader import OdysseyTrader


def main():
    print("=" * 60)
    print("Odyssey Agent Skills - Token Launch Example")
    print("=" * 60)
    
    # Initialize launcher and trader
    launcher = OdysseyTrader()
    
    # Example: Calculate first buy
    print("\n[1] Bonding Curve Price Calculation")
    print("-" * 40)
    
    test_amounts = [1.0, 10.0, 50.0, 100.0]
    
    print(f"{'SUI Input':<15} {'Tokens Received':<20} {'Price per Token':<15}")
    print("-" * 50)
    
    for sui_amount in test_amounts:
        tokens_raw, tokens_display = launcher.calculate_buy_tokens(sui_amount)
        price = sui_amount / tokens_display if tokens_display > 0 else 0
        print(f"{sui_amount:<15.2f} {tokens_display:<20,.2f} {price:<15.10f}")
    
    # Example: Launch parameters
    print("\n[2] Token Launch Parameters")
    print("-" * 40)
    
    params = LaunchParams(
        token_name="AI Agent Token",
        ticker="AAGT",
        description="A token launched by an autonomous AI agent on Odyssey",
        first_buy_sui=50.0,
        migrate_to=0,  # Cetus
        target_raise_sui=5000.0,
        twitter="https://twitter.com/aagent",
        telegram="https://t.me/aagent",
        website="https://aagent.xyz",
    )
    
    print(f"Token Name: {params.token_name}")
    print(f"Ticker: ${params.ticker}")
    print(f"Description: {params.description[:50]}...")
    print(f"First Buy: {params.first_buy_sui} SUI")
    print(f"Migrate to: {'Cetus' if params.migrate_to == 0 else 'Turbos'}")
    print(f"Target Raise: {params.target_raise_sui} SUI")
    
    # Validate parameters
    print("\n[3] Parameter Validation")
    print("-" * 40)
    
    error = launcher.validate_buy(params.first_buy_sui)
    if error:
        print(f"Validation error: {error}")
    else:
        print("Parameters valid!")
    
    # Dry run launch
    print("\n[4] Dry Run - Token Launch")
    print("-" * 40)
    
    # For dry run, use the trader to calculate
    tokens_raw, tokens_display = launcher.calculate_buy_tokens(params.first_buy_sui)
    
    print(f"First buy amount: {params.first_buy_sui} SUI")
    print(f"Expected tokens: {tokens_display:,} AAGT")
    print(f"Effective price: {params.first_buy_sui / tokens_display:.10f} SUI per token")
    print(f"\nDry run successful!")
    print("(No actual transactions were submitted to the blockchain)")
    
    print("\n" + "=" * 60)
    print("Next Steps:")
    print("=" * 60)
    print("""
1. Connect wallet (set WALLET_ADDRESS env var)
2. Fund wallet with enough SUI for:
   - Pool creation fee: ~0.01 SUI
   - First buy: 50+ SUI
   - Gas: ~0.05 SUI
   
3. Execute for real:
   - launcher.launch_token(params)
   
4. Monitor pool at Odyssey:
   - Pool ID from transaction result
   - Track bonding curve progress
   - Manage graduation to DEX
""")


if __name__ == "__main__":
    main()
