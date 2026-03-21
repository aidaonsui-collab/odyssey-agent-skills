#!/usr/bin/env python3
"""
Odyssey CLI - Simple command line interface

Usage:
    python -m odyssey_agent_skills launch --name "My Token" --ticker MINE --sui 50
    python -m odyssey_agent_skills buy --pool 0x... --token 0x... --sui 10
    python -m odyssey_agent_skills sell --pool 0x... --token 0x... --amount 1000
    python -m odyssey_agent_skills price --sui 10
"""

import argparse
import sys
import os

# Add skills to path
sys.path.insert(0, '../skills/sui-token-launch')
sys.path.insert(0, '../skills/sui-bonding-curve-trade')

from sui_token_launch.launcher import OdysseyLauncher, LaunchParams
from sui_bonding_curve_trade.trader import OdysseyTrader


def cmd_price(args):
    """Calculate price for SUI amount."""
    trader = OdysseyTrader()
    tokens_raw, tokens_display = trader.calculate_buy_tokens(args.sui)
    price = args.sui / tokens_display if tokens_display > 0 else 0
    
    print(f"\n💰 Price Calculation")
    print(f"   SUI Input: {args.sui}")
    print(f"   Tokens: {tokens_display:,.2f}")
    print(f"   Price: {price:.10f} SUI per token")
    
    # Also show sell price for same amount
    sui_out, sui_display = trader.calculate_sell_sui(tokens_display)
    print(f"\n📊 If you sell {tokens_display:,.2f} tokens:")
    print(f"   SUI Out: {sui_display:.6f}")
    print(f"   Price Impact: {((args.sui - sui_display) / args.sui * 100):.2f}%")


def cmd_launch(args):
    """Launch a new token."""
    launcher = OdysseyLauncher()
    
    # Build params
    params = LaunchParams(
        token_name=args.name,
        ticker=args.ticker.upper(),
        description=args.description or f"{args.name} token on Odyssey",
        first_buy_sui=args.sui,
        migrate_to=0 if args.migrate_to.lower() == "cetus" else 1,
        target_raise_sui=args.target,
        twitter=args.twitter or "",
        telegram=args.telegram or "",
        website=args.website or "",
    )
    
    print(f"\n🚀 Launching Token")
    print(f"   Name: {params.token_name}")
    print(f"   Ticker: ${params.ticker}")
    print(f"   First Buy: {params.first_buy_sui} SUI")
    print(f"   Target Raise: {params.target_raise_sui} SUI")
    print(f"   Migrate To: {params.migrate_to}")
    
    # Validate
    error = launcher.validate_params(params)
    if error:
        print(f"\n❌ Validation failed: {error}")
        sys.exit(1)
    
    # Calculate tokens
    tokens = launcher.calculate_tokens_display(params.first_buy_sui)
    print(f"   Expected Tokens: {tokens:,.2f}")
    
    if args.dry_run:
        print(f"\n✅ Dry run successful (no tx submitted)")
        sys.exit(0)
    
    # Execute
    result = launcher.launch_token(params)
    if result.success:
        print(f"\n✅ Launched! Pool: {result.pool_id}")
        print(f"   Digest: {result.digest}")
        print(f"   Tokens: {result.tokens_received:,.2f}")
    else:
        print(f"\n❌ Launch failed: {result.error}")
        sys.exit(1)


def cmd_buy(args):
    """Buy tokens from a pool."""
    trader = OdysseyTrader()
    
    print(f"\n🛒 Buy Order")
    print(f"   Pool: {args.pool}")
    print(f"   Token: {args.token}")
    print(f"   SUI: {args.sui}")
    
    # Validate
    error = trader.validate_buy(args.sui)
    if error:
        print(f"\n❌ Validation failed: {error}")
        sys.exit(1)
    
    # Calculate
    tokens_raw, tokens_display = trader.calculate_buy_tokens(args.sui)
    price = args.sui / tokens_display if tokens_display > 0 else 0
    
    print(f"   Tokens: {tokens_display:,.2f}")
    print(f"   Price: {price:.10f} SUI")
    
    if args.dry_run:
        print(f"\n✅ Dry run successful (no tx submitted)")
        sys.exit(0)
    
    # Execute
    result = trader.buy(args.pool, args.token, args.sui)
    if result.success:
        print(f"\n✅ Bought! Digest: {result.digest}")
    else:
        print(f"\n❌ Buy failed: {result.error}")
        sys.exit(1)


def cmd_sell(args):
    """Sell tokens back to pool."""
    trader = OdysseyTrader()
    
    print(f"\n📤 Sell Order")
    print(f"   Pool: {args.pool}")
    print(f"   Token: {args.token}")
    print(f"   Amount: {args.amount}")
    
    # Validate
    error = trader.validate_sell(args.amount)
    if error:
        print(f"\n❌ Validation failed: {error}")
        sys.exit(1)
    
    # Calculate
    sui_mist, sui_display = trader.calculate_sell_sui(args.amount)
    price = sui_display / args.amount if args.amount > 0 else 0
    
    print(f"   SUI Out: {sui_display:.6f}")
    print(f"   Price: {price:.10f} SUI")
    
    if args.dry_run:
        print(f"\n✅ Dry run successful (no tx submitted)")
        sys.exit(0)
    
    # Execute
    result = trader.sell(args.pool, args.token, args.amount)
    if result.success:
        print(f"\n✅ Sold! Digest: {result.digest}")
    else:
        print(f"\n❌ Sell failed: {result.error}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Odyssey Agent CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m odyssey_agent_skills price --sui 10
  python -m odyssey_agent_skills launch --name "My Coin" --ticker MINE --sui 50
  python -m odyssey_agent_skills buy --pool 0x123 --token 0x456 --sui 10 --dry-run
  python -m odyssey_agent_skills sell --pool 0x123 --token 0x456 --amount 1000 --dry-run
        """
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Price command
    price_parser = subparsers.add_parser('price', help='Calculate price for SUI amount')
    price_parser.add_argument('--sui', type=float, default=10.0, help='SUI amount')
    
    # Launch command
    launch_parser = subparsers.add_parser('launch', help='Launch a new token')
    launch_parser.add_argument('--name', required=True, help='Token name')
    launch_parser.add_argument('--ticker', required=True, help='Ticker symbol')
    launch_parser.add_argument('--sui', type=float, default=50.0, help='First buy amount')
    launch_parser.add_argument('--description', help='Token description')
    launch_parser.add_argument('--target', type=float, default=2000.0, help='Target raise')
    launch_parser.add_argument('--migrate-to', dest='migrate_to', default='cetus', 
                              choices=['cetus', 'turbos'], help='DEX to migrate to')
    launch_parser.add_argument('--twitter', help='Twitter URL')
    launch_parser.add_argument('--telegram', help='Telegram URL')
    launch_parser.add_argument('--website', help='Website URL')
    launch_parser.add_argument('--dry-run', action='store_true', help='Simulate only')
    
    # Buy command
    buy_parser = subparsers.add_parser('buy', help='Buy tokens from pool')
    buy_parser.add_argument('--pool', required=True, help='Pool ID')
    buy_parser.add_argument('--token', required=True, help='Token type')
    buy_parser.add_argument('--sui', type=float, required=True, help='SUI amount')
    buy_parser.add_argument('--dry-run', action='store_true', help='Simulate only')
    
    # Sell command
    sell_parser = subparsers.add_parser('sell', help='Sell tokens to pool')
    sell_parser.add_argument('--pool', required=True, help='Pool ID')
    sell_parser.add_argument('--token', required=True, help='Token type')
    sell_parser.add_argument('--amount', type=float, required=True, help='Token amount')
    sell_parser.add_argument('--dry-run', action='store_true', help='Simulate only')
    
    args = parser.parse_args()
    
    if args.command == 'price':
        cmd_price(args)
    elif args.command == 'launch':
        cmd_launch(args)
    elif args.command == 'buy':
        cmd_buy(args)
    elif args.command == 'sell':
        cmd_sell(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
