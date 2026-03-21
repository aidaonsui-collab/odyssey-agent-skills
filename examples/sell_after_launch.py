#!/usr/bin/env python3
"""
Example: Sell After Launch

Demonstrates:
1. Launching a token
2. Waiting for price appreciation
3. Selling tokens at a profit

Usage:
    python examples/sell_after_launch.py --dry-run
"""

import sys
sys.path.insert(0, '../skills/sui-token-launch')
sys.path.insert(0, '../skills/sui-bonding-curve-trade')

from sui_token_launch.launcher import OdysseyLauncher, LaunchParams
from sui_bonding_curve_trade.trader import OdysseyTrader


def simulate_price_movement(initial_sui: float, price_multiplier: float) -> float:
    """
    Simulate price moving up due to buys.
    
    Args:
        initial_sui: Initial SUI in pool
        price_multiplier: How much the price has increased (1.5 = 50% up)
        
    Returns:
        New SUI value in pool
    """
    return initial_sui * price_multiplier


def calculate_profit_loss(
    tokens_bought: float,
    initial_price: float,
    current_price: float
) -> tuple:
    """
    Calculate P&L from token purchase.
    
    Args:
        tokens_bought: Number of tokens bought
        initial_price: Price at time of purchase (SUI per token)
        current_price: Current price (SUI per token)
        
    Returns:
        Tuple of (profit_loss_sui, profit_loss_percent)
    """
    cost_basis = tokens_bought * initial_price
    current_value = tokens_bought * current_price
    pnl_sui = current_value - cost_basis
    pnl_percent = (pnl_sui / cost_basis * 100) if cost_basis > 0 else 0
    return pnl_sui, pnl_percent


def main():
    print("=" * 60)
    print("ODYSSEY - SELL AFTER LAUNCH EXAMPLE")
    print("=" * 60)
    
    # Setup
    launcher = OdysseyLauncher()
    trader = OdysseyTrader()
    
    # Launch params
    first_buy_sui = 50.0
    params = LaunchParams(
        token_name="Moonbag Token",
        ticker="MOON",
        description="A moonbag token",
        first_buy_sui=first_buy_sui,
        migrate_to=0,  # Cetus
        target_raise_sui=5000.0
    )
    
    # Calculate initial purchase
    tokens_bought_raw, tokens_bought = launcher.calculate_buy_tokens(first_buy_sui)
    initial_price = first_buy_sui / tokens_bought
    
    print(f"\n📊 INITIAL STATE")
    print(f"   First buy: {first_buy_sui} SUI")
    print(f"   Tokens received: {tokens_bought:,.2f} MOON")
    print(f"   Entry price: {initial_price:.10f} SUI/token")
    
    # Simulate different price scenarios
    scenarios = [
        ("After 10 more SUI buys", 1.2),   # 20% price increase
        ("After 50 more SUI buys", 1.5),   # 50% price increase
        ("After 100 more SUI buys", 2.0),  # 100% price increase
        ("Big buyer enters", 3.0),           # 200% price increase
    ]
    
    print(f"\n📈 PRICE SCENARIOS")
    print("-" * 60)
    
    for scenario_name, multiplier in scenarios:
        # Simulate new pool state
        pool_sui = first_buy_sui * multiplier
        
        # What would we get if we sell now?
        sui_out, sui_out_display = trader.calculate_sell_sui(tokens_bought)
        current_price = sui_out_display / tokens_bought
        
        pnl_sui, pnl_pct = calculate_profit_loss(
            tokens_bought, initial_price, current_price
        )
        
        print(f"\n🎯 {scenario_name}")
        print(f"   Pool value: {pool_sui:.2f} SUI")
        print(f"   Current price: {current_price:.10f} SUI/token")
        print(f"   If you sell {tokens_bought:,.2f} tokens:")
        print(f"   → SUI out: {sui_out_display:.6f}")
        print(f"   → P&L: {pnl_sui:+.6f} SUI ({pnl_pct:+.2f}%)")
        
        if pnl_sui > 0:
            print(f"   ✅ PROFIT!")
        else:
            print(f"   ❌ LOSS (price impact from your own selling)")
    
    # Timing consideration
    print(f"\n" + "=" * 60)
    print("⏰ TIMING CONSIDERATIONS")
    print("=" * 60)
    print("""
When to consider selling:

1. TAKE PROFITS
   - Sell 25-50% of holdings when price doubles
   - Let the rest ride with stop-loss

2. REBALANCE
   - If a position grows to >10% of portfolio, trim down
   - Diversify into other opportunities

3. GRADUATION
   - When token migrates to Cetus/Turbos, bonding curve sells may be limited
   - Consider selling before or at migration

4. RED FLAGS
   - Team/wallet dumps (check on Explorer)
   - Volume drying up
   - Competitor tokens launching better

Remember: The bonding curve means larger sells = more price impact!
    """)
    
    print("=" * 60)
    print("\nNOTE: This is a simulation. Actual trading involves")
    print("slippage, fees, and blockchain finality.")
    print("=" * 60)


if __name__ == "__main__":
    main()
