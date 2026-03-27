#!/usr/bin/env python3
"""
Odyssey Trade — Buy & Sell on Bonding Curve Pools

Usage:
    # Buy 10 SUI worth of tokens
    PRIVATE_KEY=suiprivk1... python trade.py buy --pool 0x3ada... --sui 10

    # Sell 1000 tokens
    PRIVATE_KEY=suiprivk1... python trade.py sell --pool 0x3ada... --tokens 1000

    # Estimate (no gas spent)
    python trade.py buy --pool 0x3ada... --sui 10 --dry-run
    python trade.py sell --pool 0x3ada... --tokens 1000 --dry-run

    # Check pool price
    python trade.py price --pool 0x3ada...
"""

import argparse
import asyncio
import os
import time

import httpx

# ── Contract addresses (v7, live mainnet) ────────────────────────────────────
PACKAGE   = "0xf1c7fe9b6ad3c243f794d41e87fab502883d5fc27e005d72e94fe64bbf08c69b"
CLOCK     = "0x0000000000000000000000000000000000000000000000000000000000000006"
SUI_TYPE  = "0x2::sui::SUI"
RPC_URL   = os.getenv("SUI_RPC_URL", "https://fullnode.mainnet.sui.io")

SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", "200"))   # 2% default
GAS_BUDGET   = 100_000_000                              # 0.1 SUI


# ── RPC ───────────────────────────────────────────────────────────────────────

async def rpc(method: str, params: list) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(RPC_URL, json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params
        })
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data["result"]


async def get_pool(pool_id: str) -> dict:
    """Fetch live pool state."""
    result = await rpc("sui_getObject", [pool_id, {"showContent": True, "showType": True}])
    data = result["data"]
    f = data["content"]["fields"]

    # Extract coin type from pool type: Pool<COIN_TYPE>
    type_str = data["content"]["type"]
    import re
    m = re.search(r"Pool<(.+)>", type_str)
    coin_type = m.group(1) if m else ""

    v_sui   = int(f["virtual_sui_reserves"])
    v_token = int(f["virtual_token_reserves"])
    real_sui = int(f["real_sui_reserves"]["fields"]["balance"])
    threshold = int(f["threshold"])

    return {
        "pool_id":       pool_id,
        "coin_type":     coin_type,
        "virtual_sui":   v_sui,
        "virtual_token": v_token,
        "real_sui":      real_sui,
        "threshold":     threshold,
        "is_completed":  f["is_completed"],
        "progress":      real_sui / threshold * 100,
        "price_sui":     (v_sui / 1e9) / (v_token / 1e6),
    }


async def get_token_coins(address: str, coin_type: str) -> list[dict]:
    result = await rpc("suix_getCoins", [address, coin_type, None, 50])
    return result.get("data", [])


async def get_sui_balance(address: str) -> int:
    result = await rpc("suix_getBalance", [address, SUI_TYPE])
    return int(result.get("totalBalance", 0))


# ── Math ──────────────────────────────────────────────────────────────────────

def tokens_out(sui_mist: int, v_sui: int, v_token: int) -> int:
    """Raw token units out for sui_mist input (before fee)."""
    return (sui_mist * v_token) // (v_sui + sui_mist)


def sui_out(token_raw: int, v_sui: int, v_token: int) -> int:
    """Raw SUI mist out for token_raw input (before fee)."""
    return (token_raw * v_sui) // (v_token + token_raw)


def apply_fee(amount: int, fee_bps: int = 200) -> int:
    """Amount after 2% fee deduction."""
    return amount * (10000 - fee_bps) // 10000


def min_out(expected: int, slippage_bps: int = SLIPPAGE_BPS) -> int:
    return expected * (10000 - slippage_bps) // 10000


def price_impact(sui_mist: int, v_sui: int) -> float:
    """Estimate price impact percentage."""
    return sui_mist / v_sui * 100


# ── Wallet ────────────────────────────────────────────────────────────────────

def load_signer():
    pk = os.getenv("PRIVATE_KEY", "").strip()
    if not pk:
        raise ValueError("PRIVATE_KEY env var not set")

    from pysui import SuiConfig, SyncClient
    from pysui.sui.sui_crypto import keypair_from_keystring

    if not pk.startswith("suiprivk1"):
        raise ValueError("PRIVATE_KEY must be in suiprivk1... format (Sui bech32 private key)")

    cfg = SuiConfig.user_config(rpc_url=RPC_URL, prv_keys=[pk])
    client = SyncClient(cfg)
    kp = keypair_from_keystring(pk)
    address = kp.public_key.get_sui_address().address
    return client, address


# ── Buy ───────────────────────────────────────────────────────────────────────

async def estimate_buy(pool: dict, sui_float: float) -> dict:
    sui_mist = int(sui_float * 1e9)
    fee_mist = sui_mist * 200 // 10000
    net_mist = sui_mist - fee_mist

    raw_tokens = tokens_out(net_mist, pool["virtual_sui"], pool["virtual_token"])
    tokens_float = raw_tokens / 1e6
    impact = price_impact(net_mist, pool["virtual_sui"])
    min_tokens = min_out(raw_tokens)

    new_price = ((pool["virtual_sui"] + net_mist) / 1e9) / \
                ((pool["virtual_token"] - raw_tokens) / 1e6)

    return {
        "sui_in":       sui_float,
        "fee_sui":      fee_mist / 1e9,
        "tokens_out":   tokens_float,
        "min_tokens":   min_tokens / 1e6,
        "raw_min":      min_tokens,
        "price_before": pool["price_sui"],
        "price_after":  new_price,
        "impact_pct":   impact,
    }


def execute_buy(client, pool: dict, sui_float: float, est: dict) -> str:
    from pysui.sui.sui_txn.sync_transaction import SuiTransaction
    from pysui.sui.sui_types.scalars import SuiU64, ObjectID

    sui_mist = int(sui_float * 1e9)

    txn = SuiTransaction(client=client)

    [payment] = txn.split_coin(coin=txn.gas, amounts=[sui_mist])

    [token_coin] = txn.move_call(
        target=f"{PACKAGE}::moonbags::buy",
        arguments=[
            ObjectID(pool["pool_id"]),
            payment,
            SuiU64(est["raw_min"]),
        ],
        type_arguments=[pool["coin_type"], SUI_TYPE],
    )

    # Transfer received tokens to sender
    txn.transfer_objects(transfers=[token_coin], recipient=client.config.active_address)
    txn.set_gas_budget(GAS_BUDGET)

    result = client.execute(txn)
    if result.is_err():
        raise RuntimeError(f"Buy TX failed: {result.result_string}")

    return result.result_data.digest


# ── Sell ──────────────────────────────────────────────────────────────────────

async def estimate_sell(pool: dict, tokens_float: float) -> dict:
    token_raw = int(tokens_float * 1e6)

    gross_sui = sui_out(token_raw, pool["virtual_sui"], pool["virtual_token"])
    fee_mist  = gross_sui * 200 // 10000
    net_sui   = gross_sui - fee_mist
    min_sui   = min_out(net_sui)

    new_price = ((pool["virtual_sui"] - gross_sui) / 1e9) / \
                ((pool["virtual_token"] + token_raw) / 1e6)

    return {
        "tokens_in":    tokens_float,
        "token_raw":    token_raw,
        "sui_gross":    gross_sui / 1e9,
        "fee_sui":      fee_mist / 1e9,
        "sui_net":      net_sui / 1e9,
        "min_sui":      min_sui,
        "raw_min":      min_sui,
        "price_before": pool["price_sui"],
        "price_after":  new_price,
    }


def execute_sell(client, pool: dict, tokens_float: float, est: dict) -> str:
    from pysui.sui.sui_txn.sync_transaction import SuiTransaction
    from pysui.sui.sui_types.scalars import SuiU64, ObjectID

    token_raw = est["token_raw"]
    address   = str(client.config.active_address)

    # Fetch token coins synchronously
    token_coins = asyncio.run(get_token_coins(address, pool["coin_type"]))
    if not token_coins:
        raise RuntimeError(f"No {pool['coin_type']} coins in wallet")

    total_balance = sum(int(c["balance"]) for c in token_coins)
    if total_balance < token_raw:
        raise RuntimeError(
            f"Insufficient tokens: have {total_balance / 1e6:.2f}, need {tokens_float:.2f}"
        )

    txn = SuiTransaction(client=client)

    # Merge all token coins into one
    primary = token_coins[0]["coinObjectId"]
    if len(token_coins) > 1:
        txn.merge_coins(
            merge_to=ObjectID(primary),
            merge_from=[ObjectID(c["coinObjectId"]) for c in token_coins[1:]],
        )

    # Split exact amount to sell
    [sell_coin] = txn.split_coin(
        coin=ObjectID(primary),
        amounts=[token_raw],
    )

    [sui_coin] = txn.move_call(
        target=f"{PACKAGE}::moonbags::sell",
        arguments=[
            ObjectID(pool["pool_id"]),
            sell_coin,
            SuiU64(est["raw_min"]),
        ],
        type_arguments=[pool["coin_type"], SUI_TYPE],
    )

    txn.transfer_objects(transfers=[sui_coin], recipient=client.config.active_address)
    txn.set_gas_budget(GAS_BUDGET)

    result = client.execute(txn)
    if result.is_err():
        raise RuntimeError(f"Sell TX failed: {result.result_string}")

    return result.result_data.digest


# ── CLI handlers ──────────────────────────────────────────────────────────────

async def cmd_buy(args):
    pool = await get_pool(args.pool)

    if pool["is_completed"]:
        print("❌ Pool has graduated to DEX — trade there instead")
        return

    est = await estimate_buy(pool, args.sui)

    print(f"\n💸 BUY ESTIMATE")
    print(f"   Pool:        {args.pool[:20]}...")
    print(f"   Coin:        {pool['coin_type'].split('::')[-1]}")
    print(f"   Pay:         {est['sui_in']:.4f} SUI (incl. {est['fee_sui']:.4f} fee)")
    print(f"   Receive:     ~{est['tokens_out']:,.2f} tokens")
    print(f"   Min out:     {est['min_tokens']:,.2f} tokens ({SLIPPAGE_BPS/100:.1f}% slippage)")
    print(f"   Price before:{est['price_before']:.10f} SUI")
    print(f"   Price after: {est['price_after']:.10f} SUI")
    print(f"   Impact:      {est['impact_pct']:.2f}%")

    if est["impact_pct"] > 5:
        print(f"\n   ⚠️  High price impact ({est['impact_pct']:.1f}%) — consider smaller amount")

    if args.dry_run:
        print("\n   ℹ️  Dry run — no transaction submitted\n")
        return

    client, address = load_signer()
    bal = await get_sui_balance(address)
    needed = int(args.sui * 1e9) + GAS_BUDGET
    if bal < needed:
        print(f"\n❌ Insufficient SUI: {bal/1e9:.4f} available, {needed/1e9:.4f} needed")
        return

    print(f"\n⏳ Submitting buy transaction...")
    t = time.time()
    digest = execute_buy(client, pool, args.sui, est)
    print(f"✅ Bought in {time.time()-t:.1f}s")
    print(f"   TX: {digest}")
    print(f"   View: https://suiscan.xyz/mainnet/tx/{digest}\n")


async def cmd_sell(args):
    pool = await get_pool(args.pool)

    if pool["is_completed"]:
        print("❌ Pool has graduated to DEX — sell there instead")
        return

    est = await estimate_sell(pool, args.tokens)

    print(f"\n💰 SELL ESTIMATE")
    print(f"   Pool:        {args.pool[:20]}...")
    print(f"   Coin:        {pool['coin_type'].split('::')[-1]}")
    print(f"   Sell:        {est['tokens_in']:,.2f} tokens")
    print(f"   Receive:     ~{est['sui_net']:.4f} SUI (after {est['fee_sui']:.4f} fee)")
    print(f"   Min out:     {est['min_sui']:.4f} SUI ({SLIPPAGE_BPS/100:.1f}% slippage)")
    print(f"   Price before:{est['price_before']:.10f} SUI")
    print(f"   Price after: {est['price_after']:.10f} SUI")

    if args.dry_run:
        print("\n   ℹ️  Dry run — no transaction submitted\n")
        return

    client, address = load_signer()

    print(f"\n⏳ Submitting sell transaction...")
    t = time.time()
    digest = execute_sell(client, pool, args.tokens, est)
    print(f"✅ Sold in {time.time()-t:.1f}s")
    print(f"   TX: {digest}")
    print(f"   View: https://suiscan.xyz/mainnet/tx/{digest}\n")


async def cmd_price(args):
    pool = await get_pool(args.pool)
    sym  = pool["coin_type"].split("::")[-1]

    print(f"\n📊 {sym} Pool State")
    print(f"   Pool ID:   {args.pool}")
    print(f"   Coin type: {pool['coin_type']}")
    print(f"   Price:     {pool['price_sui']:.10f} SUI/{sym}")
    print(f"   Raised:    {pool['real_sui'] / 1e9:.4f} SUI")
    print(f"   Progress:  {pool['progress']:.2f}% to graduation")
    print(f"   Graduated: {pool['is_completed']}")
    if not pool["is_completed"]:
        rem = (pool["threshold"] - pool["real_sui"]) / 1e9
        print(f"   Remaining: {rem:.2f} SUI until DEX listing")
    print()


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Buy/sell tokens on Odyssey bonding curve")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # buy
    p_buy = sub.add_parser("buy", help="Buy tokens with SUI")
    p_buy.add_argument("--pool", "-p", required=True, help="Pool object ID")
    p_buy.add_argument("--sui",  "-s", required=True, type=float, help="SUI to spend")
    p_buy.add_argument("--slippage", type=float, default=2.0, help="Max slippage %")
    p_buy.add_argument("--dry-run", action="store_true")

    # sell
    p_sell = sub.add_parser("sell", help="Sell tokens for SUI")
    p_sell.add_argument("--pool",   "-p", required=True, help="Pool object ID")
    p_sell.add_argument("--tokens", "-t", required=True, type=float, help="Tokens to sell")
    p_sell.add_argument("--slippage", type=float, default=2.0)
    p_sell.add_argument("--dry-run", action="store_true")

    # price
    p_price = sub.add_parser("price", help="Check pool price and state")
    p_price.add_argument("--pool", "-p", required=True)

    args = parser.parse_args()

    # Set slippage if provided
    global SLIPPAGE_BPS
    if hasattr(args, "slippage"):
        SLIPPAGE_BPS = int(args.slippage * 100)

    if args.cmd == "buy":
        await cmd_buy(args)
    elif args.cmd == "sell":
        await cmd_sell(args)
    elif args.cmd == "price":
        await cmd_price(args)


if __name__ == "__main__":
    asyncio.run(main())
