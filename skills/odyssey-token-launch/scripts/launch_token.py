#!/usr/bin/env python3
"""
Odyssey Token Launch Script — Direct On-chain via PTB

Launches a token on Odyssey 2.0 bonding curve with:
  TX 1: Publish unique coin package (bytecode patching)
  TX 2: Create bonding curve pool with first buy

Requires: pysui >= 0.50.0  OR  direct JSON-RPC via httpx
"""

import argparse
import asyncio
import base64
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Optional

import httpx

# ── Contract addresses ────────────────────────────────────────────────────────
PACKAGE    = "0xf1c7fe9b6ad3c243f794d41e87fab502883d5fc27e005d72e94fe64bbf08c69b"
CONFIG     = "0xfb774b5c4902d7d39e899388f520db0e2b1a6dca72687803b894d7d67eca9326"
STAKE_CFG  = "0x312216a4b80aa2665be3539667ef3749fafb0bde8c8ff529867ca0f0dc13bc18"
LOCK_CFG   = "0x7b3f064b45911affde459327ba394f2aa8782539d9b988c4986ee71c5bd34059"
CLOCK      = "0x0000000000000000000000000000000000000000000000000000000000000006"
SUI_META   = "0x9258181f5ceac8dbffb7030890243caed69a9599d2886d957a9cb7656af3bdb3"
RPC_URL    = os.getenv("SUI_RPC_URL", "https://fullnode.mainnet.sui.io")

# Coin template bytecode — COIN_TEMPLATE / coin_template / Token / Token Name
# are placeholder strings that get patched at runtime with the actual ticker
COIN_BYTECODE_B64 = (
    "oRzrCwYAAAAKAQAMAgweAyocBEYIBU5RB58BqwEIygJgBqoDGwrFAwUMygMtAAcBDAIGAg8CEAIRAAACAAEC"
    "BwEAAAIBDAEAAQIDDAEAAQQEAgAFBQcAAAoAAQABCwEEAQACCAYHAQIDDQsBAQwEDggJAAEDAgUDCgMMAgq"
    "AABwgEAAILAgEIAAsDAQgAAQgFAQsBAQkAAQgABwkAAgoCCgIKAgsBAQgFBwgEAgsDAQkACwIBCQABBggE"
    "AQUBCwIBCAACCQAFAQsDAQgADUNPSU5fVEVNUExBVEUMQ29pbk1ldGFkYXRhBk9wdGlvbgtUcmVhc3VyeU"
    "NhcAlUeENvbnRleHQDVXJsBGNvaW4NY29pbl90ZW1wbGF0ZQ9jcmVhdGVfY3VycmVuY3kLZHVtbXlfZmll"
    "bGQEaW5pdARub25lBm9wdGlvbg9wdWJsaWNfdHJhbnNmZXIGc2VuZGVyCHRyYW5zZmVyCnR4X2NvbnRleH"
    "QDdXJsV6zO2JBHJ3Lh42Zr3Y84+I3JoNOWqP5B/vpOkbfvtSIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACCgIGBVRva2VuCgILClRva2VuIE5hbWUKAgEA"
    "AAIBCQEAAAAAAhULADEGBwAHAQcCOAAKATgBDAIMAwsCCgEuEQQ4AgsDCwEuEQQ4AwIA"
)

# ── Bonding curve math ────────────────────────────────────────────────────────
# Initial pool constants from Configuration object on mainnet.
# NOTE: These are STARTING values. A live pool's reserves shift with every trade.
# For accurate buy/sell estimates, always fetch live pool state from chain.
V_TOKEN_INIT = 533_333_333_500_000   # initial virtual token reserves (6 decimals)
V_SUI_INIT   = 2_000_000_000_000     # initial virtual SUI reserves (= graduation threshold, 9 dec)
TOKEN_DEC    = 6
SUI_DEC      = 9


def tokens_out_estimate(sui_mist: int) -> float:
    """Estimate tokens from a NEW pool (uses initial reserves). Fetch live state for accuracy."""
    raw = (sui_mist * V_TOKEN_INIT) // (V_SUI_INIT + sui_mist)
    return raw / 10 ** TOKEN_DEC


def current_price_new_pool() -> float:
    """Starting price in SUI per token (new pool only)."""
    return (V_SUI_INIT / 10 ** SUI_DEC) / (V_TOKEN_INIT / 10 ** TOKEN_DEC)



# ── Bytecode patching ─────────────────────────────────────────────────────────

def patch_bytecode(symbol: str, name: str) -> str:
    """
    Patch coin_template bytecode with actual ticker symbol and token name.
    Replaces length-prefixed placeholder strings in-place.
    Returns patched base64.
    """
    sym_upper = symbol.upper().replace(" ", "")
    sym_lower = sym_upper.lower()

    data = bytearray(base64.b64decode(COIN_BYTECODE_B64))

    def find_and_replace(placeholder: str, replacement: str):
        enc_old = placeholder.encode()
        enc_new = replacement.encode()
        target  = bytes([len(enc_old)]) + enc_old
        pos = bytes(data).find(target)
        if pos == -1:
            raise ValueError(f"Placeholder '{placeholder}' not found in bytecode")
        new_bytes = bytes([len(enc_new)]) + enc_new
        data[pos : pos + len(target)] = new_bytes

    # Apply back-to-front so earlier offsets stay valid
    replacements = [
        ("COIN_TEMPLATE", sym_upper),
        ("coin_template", sym_lower),
        ("Token Name",    name),
        ("Token",         sym_upper),
    ]
    # Sort by position descending
    with_pos = []
    tmp = bytearray(data)
    for ph, rep in replacements:
        enc = ph.encode()
        target = bytes([len(enc)]) + enc
        pos = bytes(tmp).find(target)
        if pos == -1:
            raise ValueError(f"'{ph}' not found")
        with_pos.append((pos, ph, rep))

    for pos, ph, rep in sorted(with_pos, key=lambda x: -x[0]):
        enc_old = ph.encode()
        enc_new = rep.encode()
        target  = bytes([len(enc_old)]) + enc_old
        new_bytes = bytes([len(enc_new)]) + enc_new
        data[pos : pos + len(target)] = new_bytes

    return base64.b64encode(bytes(data)).decode()


# ── RPC helpers ───────────────────────────────────────────────────────────────

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


async def get_sui_balance(address: str) -> int:
    result = await rpc("suix_getBalance", [address, "0x2::sui::SUI"])
    return int(result.get("totalBalance", 0))


async def get_pool_state(pool_id: str) -> dict:
    result = await rpc("sui_getObject", [pool_id, {"showContent": True}])
    fields = result["data"]["content"]["fields"]
    return {
        "virtual_sui":   int(fields["virtual_sui_reserves"]),
        "virtual_token": int(fields["virtual_token_reserves"]),
        "real_sui":      int(fields["real_sui_reserves"]["fields"]["balance"]),
        "threshold":     int(fields["threshold"]),
        "is_completed":  fields["is_completed"],
        "progress":      int(fields["real_sui_reserves"]["fields"]["balance"]) / int(fields["threshold"]) * 100,
    }


# ── Launch params ─────────────────────────────────────────────────────────────

@dataclass
class LaunchParams:
    name:             str
    symbol:           str
    description:      str   = ""
    image_url:        str   = ""
    twitter:          str   = ""
    telegram:         str   = ""
    website:          str   = ""
    first_buy_sui:    float = 50.0
    target_raise_sui: float = 2000.0
    migrate_to:       int   = 1      # 1=Turbos (only supported currently)


# ── Main launch flow ──────────────────────────────────────────────────────────

async def simulate_launch(params: LaunchParams):
    """Print what the launch would do without executing."""
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  🚀 ODYSSEY TOKEN LAUNCH — DRY RUN")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Name:         {params.name}")
    print(f"  Symbol:       ${params.symbol.upper()}")
    print(f"  Description:  {params.description or '(none)'}")
    print(f"  First buy:    {params.first_buy_sui} SUI")
    print(f"  Target raise: {params.target_raise_sui} SUI")
    print(f"  Migrate to:   {'Turbos' if params.migrate_to == 1 else 'Cetus'}")
    print()

    est_tokens = tokens_out_estimate(int(params.first_buy_sui * 1e9))
    price      = current_price_new_pool()
    fee        = params.first_buy_sui * 0.02

    print(f"  📊 Estimated tokens from first buy: {est_tokens:,.2f} ${params.symbol.upper()}")
    print(f"  💰 Current price:                  {price:.10f} SUI")
    print(f"  💸 Platform fee (2%):              {fee:.4f} SUI")
    print()
    print("  TX 1: Publish coin package (unique bytecode per ticker)")
    print(f"         → Coin type: 0x<NEW_PKG>::{params.symbol.lower()}::{params.symbol.upper()}")
    print("  TX 2: create_and_lock_first_buy_with_fee")
    print(f"         → Pool created on Odyssey bonding curve")
    print(f"         → {est_tokens:,.2f} ${params.symbol.upper()} locked for creator")
    print()

    # Validate bytecode patching
    try:
        patched = patch_bytecode(params.symbol, params.name)
        decoded = base64.b64decode(patched)
        sym_ok  = params.symbol.upper().encode() in decoded
        mod_ok  = params.symbol.lower().encode() in decoded
        tmpl_ok = b"COIN_TEMPLATE" not in decoded
        print(f"  ✅ Bytecode patching: {'OK' if sym_ok and mod_ok and tmpl_ok else 'FAILED'}")
        print(f"     Struct: {params.symbol.upper()} ✓" if sym_ok else "     Struct: FAILED ✗")
        print(f"     Module: {params.symbol.lower()} ✓" if mod_ok else "     Module: FAILED ✗")
        print(f"     Template removed: ✓" if tmpl_ok else "     Template still present: ✗")
    except Exception as e:
        print(f"  ❌ Bytecode patching failed: {e}")

    print()
    print("  ℹ️  Run without --dry-run to execute on-chain")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Launch a token on Odyssey 2.0 bonding curve"
    )
    parser.add_argument("--name",        required=True,  help="Token name (e.g. 'Moon Dog')")
    parser.add_argument("--symbol", "-t",required=True,  help="Ticker symbol (e.g. MOON)")
    parser.add_argument("--description", default="",     help="Token description")
    parser.add_argument("--image",       default="",     help="Image URL")
    parser.add_argument("--twitter",     default="",     help="Twitter/X handle or URL")
    parser.add_argument("--telegram",    default="",     help="Telegram URL")
    parser.add_argument("--website",     default="",     help="Website URL")
    parser.add_argument("--sui",    "-s",type=float, default=50.0,   help="First buy SUI amount")
    parser.add_argument("--target",      type=float, default=2000.0, help="Graduation target (SUI)")
    parser.add_argument("--migrate",     choices=["turbos"], default="turbos",
                        help="DEX to graduate to (turbos only currently)")
    parser.add_argument("--pool",        help="Pool ID to query state (no launch)")
    parser.add_argument("--dry-run",     action="store_true", help="Simulate — no transactions")
    args = parser.parse_args()

    # Query pool state mode
    if args.pool:
        print(f"\n📊 Pool state for {args.pool}")
        state = await get_pool_state(args.pool)
        price = (state["virtual_sui"] / 1e9) / (state["virtual_token"] / 1e6)
        print(f"  Price:      {price:.10f} SUI/token")
        print(f"  Real SUI:   {state['real_sui'] / 1e9:.4f} SUI raised")
        print(f"  Progress:   {state['progress']:.2f}%")
        print(f"  Graduated:  {state['is_completed']}")
        return

    params = LaunchParams(
        name=args.name,
        symbol=args.symbol.upper().replace(" ", ""),
        description=args.description,
        image_url=args.image,
        twitter=args.twitter,
        telegram=args.telegram,
        website=args.website,
        first_buy_sui=args.sui,
        target_raise_sui=args.target,
        migrate_to=1,  # Turbos
    )

    if args.dry_run:
        await simulate_launch(params)
        return

    # Live execution requires a Sui wallet integration
    # Use pysui, suibase, or build your own PTB signer
    print("\n❌ Live execution not implemented in this script.")
    print("   The launch flow requires two on-chain transactions:")
    print("   1. tx.publish(patched_bytecode) → get TreasuryCap + packageId")
    print("   2. tx.moveCall(create_and_lock_first_buy_with_fee, ...)")
    print()
    print("   Integrate with:")
    print("   - pysui: https://github.com/FrankC01/pysui")
    print("   - @mysten/sui SDK (TypeScript) — see lib/coinPublish.ts in theodyssey2")
    print()
    print("   Run with --dry-run to validate parameters.\n")


if __name__ == "__main__":
    asyncio.run(main())
