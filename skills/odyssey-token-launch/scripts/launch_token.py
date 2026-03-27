#!/usr/bin/env python3
"""
Odyssey Token Launch — Full On-chain Execution

Launches a unique token on Odyssey 2.0 bonding curve in two transactions:
  TX 1: Publish a unique coin package (bytecode patching — no shared template)
  TX 2: Create bonding curve pool with first buy

Result: coin type is 0x<NEW_PKG>::<ticker>::<TICKER> (e.g. 0xabc::hope::HOPE)

Requirements:
    pip install pysui httpx

Usage:
    # Dry run (validate, no gas spent)
    python launch_token.py --name "My Token" --ticker MINE --sui 50 --dry-run

    # Live launch (requires PRIVATE_KEY env var)
    PRIVATE_KEY=suiprivk1... python launch_token.py --name "My Token" --ticker MINE --sui 50

    # Query pool state
    python launch_token.py --pool 0x3ada...
"""

import argparse
import asyncio
import base64
import json
import os
import sys
import time
from dataclasses import dataclass

import httpx

# ── Contract addresses (v7, live mainnet) ────────────────────────────────────
PACKAGE   = "0xf1c7fe9b6ad3c243f794d41e87fab502883d5fc27e005d72e94fe64bbf08c69b"
CONFIG    = "0xfb774b5c4902d7d39e899388f520db0e2b1a6dca72687803b894d7d67eca9326"
STAKE_CFG = "0x312216a4b80aa2665be3539667ef3749fafb0bde8c8ff529867ca0f0dc13bc18"
LOCK_CFG  = "0x7b3f064b45911affde459327ba394f2aa8782539d9b988c4986ee71c5bd34059"
CLOCK     = "0x0000000000000000000000000000000000000000000000000000000000000006"
SUI_META  = "0x9258181f5ceac8dbffb7030890243caed69a9599d2886d957a9cb7656af3bdb3"
SUI_TYPE  = "0x2::sui::SUI"
RPC_URL   = os.getenv("SUI_RPC_URL", "https://fullnode.mainnet.sui.io")

STD_DEP   = "0x0000000000000000000000000000000000000000000000000000000000000001"
SUI_DEP   = "0x0000000000000000000000000000000000000000000000000000000000000002"

# coin_template bytecode — COIN_TEMPLATE/coin_template/Token/Token Name are patched at runtime
COIN_BYTECODE_B64 = (
    "oRzrCwYAAAAKAQAMAgweAyocBEYIBU5RB58BqwEIygJgBqoDGwrFAwUMygMtAAcBDAIGAg8CEAIRAAACAAEC"
    "BwEAAAIBDAEAAQIDDAEAAQQEAgAFBQcAAAoAAQABCwEEAQACCAYHAQIDDQsBAQwEDggJAAEDAgUDCgMMAggA"
    "BwgEAAILAgEIAAsDAQgAAQgFAQsBAQkAAQgABwkAAgoCCgIKAgsBAQgFBwgEAgsDAQkACwIBCQABBggEAQUB"
    "CwIBCAACCQAFAQsDAQgADUNPSU5fVEVNUExBVEUMQ29pbk1ldGFkYXRhBk9wdGlvbgtUcmVhc3VyeUNhcAl"
    "UeENvbnRleHQDVXJsBGNvaW4NY29pbl90ZW1wbGF0ZQ9jcmVhdGVfY3VycmVuY3kLZHVtbXlfZmllbGQEaW5"
    "pdARub25lBm9wdGlvbg9wdWJsaWNfdHJhbnNmZXIGc2VuZGVyCHRyYW5zZmVyCnR4X2NvbnRleHQDdXJsV6z"
    "O2JBHJ3Lh42Zr3Y84+I3JoNOWqP5B/vpOkbfvtSIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACCgIGBVRv"
    "a2VuCgILClRva2VuIE5hbWUKAgEAAAIBCQEAAAAAAhULADEGBwAHAQcCOAAKATgBDAIMAwsCCgEuEQQ4AgsDC"
    "wEuEQQ4AwIA"
)

# ── Bonding curve constants (initial pool state from Configuration) ────────────
V_TOKEN_INIT  = 533_333_333_500_000    # initial virtual token reserves (6 decimals)
V_SUI_INIT    = 2_000_000_000_000      # initial virtual SUI reserves (9 decimals = 2000 SUI)
GRADUATION    = 2_000_000_000_000_000  # graduation threshold mist (2000 SUI)
TOKEN_DEC     = 6
SUI_DEC       = 9


# ── Bytecode patching ─────────────────────────────────────────────────────────

def patch_bytecode(symbol: str, name: str) -> bytes:
    """
    Patch coin_template bytecode with actual ticker/name.
    Returns raw bytes (not base64).
    """
    sym_upper = symbol.upper().replace(" ", "")[:20]
    sym_lower = sym_upper.lower()
    token_name = name.strip() or sym_upper

    data = bytearray(base64.b64decode(COIN_BYTECODE_B64))

    def find_len_prefixed(d: bytearray, s: str) -> int:
        enc = s.encode()
        target = bytes([len(enc)]) + enc
        pos = bytes(d).find(target)
        if pos == -1:
            raise ValueError(f"Placeholder '{s}' not found in bytecode")
        return pos

    # Collect all patches with their positions, apply back-to-front
    replacements = [
        ("COIN_TEMPLATE", sym_upper),
        ("coin_template", sym_lower),
        ("Token Name",    token_name),
        ("Token",         sym_upper),
    ]
    patches = []
    for placeholder, replacement in replacements:
        pos = find_len_prefixed(data, placeholder)
        old_bytes = bytes([len(placeholder)]) + placeholder.encode()
        new_bytes = bytes([len(replacement)]) + replacement.encode()
        patches.append((pos, old_bytes, new_bytes))

    for pos, old, new in sorted(patches, key=lambda x: -x[0]):
        data[pos:pos + len(old)] = new

    # Verify
    result = bytes(data)
    assert sym_upper.encode() in result, "Symbol not found in patched bytecode"
    assert sym_lower.encode() in result, "Module not found in patched bytecode"
    assert b"COIN_TEMPLATE" not in result, "Placeholder still in patched bytecode"
    return result


# ── Bonding curve math ────────────────────────────────────────────────────────

def tokens_out_estimate(sui_mist: int) -> float:
    """Estimate tokens from a new pool (uses initial reserves)."""
    raw = (sui_mist * V_TOKEN_INIT) // (V_SUI_INIT + sui_mist)
    return raw / 10 ** TOKEN_DEC


def starting_price_sui() -> float:
    return (V_SUI_INIT / 10 ** SUI_DEC) / (V_TOKEN_INIT / 10 ** TOKEN_DEC)


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


async def get_sui_coins(address: str) -> list[dict]:
    result = await rpc("suix_getCoins", [address, SUI_TYPE, None, 10])
    return result.get("data", [])


async def get_pool_state(pool_id: str) -> dict:
    result = await rpc("sui_getObject", [pool_id, {"showContent": True}])
    f = result["data"]["content"]["fields"]
    real_sui = int(f["real_sui_reserves"]["fields"]["balance"])
    threshold = int(f["threshold"])
    v_sui = int(f["virtual_sui_reserves"])
    v_tok = int(f["virtual_token_reserves"])
    return {
        "virtual_sui":   v_sui,
        "virtual_token": v_tok,
        "real_sui":      real_sui,
        "threshold":     threshold,
        "is_completed":  f["is_completed"],
        "progress":      real_sui / threshold * 100,
        "price_sui":     (v_sui / 1e9) / (v_tok / 1e6),
    }


async def wait_for_tx(digest: str, max_wait: int = 30) -> dict:
    """Poll until tx is confirmed."""
    for _ in range(max_wait):
        try:
            result = await rpc("sui_getTransactionBlock", [
                digest,
                {"showEffects": True, "showObjectChanges": True}
            ])
            if result.get("effects", {}).get("status"):
                return result
        except Exception:
            pass
        await asyncio.sleep(1)
    raise TimeoutError(f"TX {digest} not confirmed after {max_wait}s")


# ── Transaction execution via pysui ──────────────────────────────────────────

def load_signer():
    """Load keypair from PRIVATE_KEY env var."""
    pk = os.getenv("PRIVATE_KEY", "").strip()
    if not pk:
        raise ValueError("PRIVATE_KEY env var not set. Export your Sui private key.")

    try:
        from pysui import SuiConfig, SyncClient
        from pysui.sui.sui_crypto import keypair_from_keystring

        if pk.startswith("suiprivk1"):
            kp = keypair_from_keystring(pk)
        else:
            # Hex format
            from pysui.sui.sui_crypto import SuiKeyPair
            from pysui.abstracts.client_keypair import SignatureScheme
            if pk.startswith("0x"):
                pk = pk[2:]
            raw = bytes.fromhex(pk[:64])
            kp = SuiKeyPair.ed25519_keypair(private_key=raw)

        cfg = SuiConfig.user_config(
            rpc_url=RPC_URL,
            prv_keys=[pk],
        )
        client = SyncClient(cfg)
        address = kp.public_key.get_sui_address().address
        return client, kp, address

    except ImportError:
        raise ImportError("pysui not installed. Run: pip install pysui")


def execute_publish_tx(client, patched_bytes: bytes, sender: str) -> dict:
    """
    TX 1: Publish the patched coin package.
    Returns objectChanges from the transaction.
    """
    from pysui.sui.sui_txn.sync_transaction import SuiTransaction
    from pysui.sui.sui_bcs import bcs

    txn = SuiTransaction(client=client)

    # Convert bytes to list[list[int]] format expected by bcs.Publish
    module_ints = list(patched_bytes)
    dep_addrs = [
        bcs.Address.from_str(STD_DEP),
        bcs.Address.from_str(SUI_DEP),
    ]

    # Call builder.publish directly with our pre-compiled bytes
    upgrade_cap = txn.builder.publish([module_ints], dep_addrs)

    # Transfer upgrade cap to sender (makes package upgradeable by sender)
    txn.transfer_objects(
        transfers=[upgrade_cap],
        recipient=sender,
    )

    txn.set_gas_budget(100_000_000)

    result = client.execute(txn)
    if result.is_err():
        raise RuntimeError(f"Publish TX failed: {result.result_string}")

    tx_data = result.result_data
    return tx_data


def extract_publish_result(tx_data, symbol: str) -> dict:
    """Extract packageId, TreasuryCap, CoinMetadata from TX 1 result."""
    changes = tx_data.object_changes if hasattr(tx_data, 'object_changes') else []

    # Handle both object types
    package_id = None
    treasury_cap_id = None
    coin_metadata_id = None

    for change in changes:
        obj_type = ""
        obj_id = ""

        if hasattr(change, 'object_type'):
            obj_type = str(change.object_type or "")
            obj_id   = str(change.object_id or "")
        elif isinstance(change, dict):
            obj_type = change.get("objectType", "")
            obj_id   = change.get("objectId", "")
            if change.get("type") == "published":
                package_id = change.get("packageId")
                continue

        if "TreasuryCap" in obj_type:
            treasury_cap_id = obj_id
        elif "CoinMetadata" in obj_type:
            coin_metadata_id = obj_id

    if not package_id:
        # Try digest-based lookup
        digest = tx_data.digest if hasattr(tx_data, 'digest') else None
        if digest:
            import asyncio
            tx = asyncio.run(wait_for_tx(digest))
            for c in tx.get("objectChanges", []):
                if c.get("type") == "published":
                    package_id = c.get("packageId")
                if "TreasuryCap" in c.get("objectType", ""):
                    treasury_cap_id = c.get("objectId")
                if "CoinMetadata" in c.get("objectType", ""):
                    coin_metadata_id = c.get("objectId")

    if not package_id:
        raise RuntimeError("Could not find packageId in TX result")

    sym = symbol.upper()
    mod = symbol.lower()
    coin_type = f"{package_id}::{mod}::{sym}"

    return {
        "package_id":       package_id,
        "coin_type":        coin_type,
        "treasury_cap_id":  treasury_cap_id,
        "coin_metadata_id": coin_metadata_id,
        "digest":           tx_data.digest if hasattr(tx_data, 'digest') else None,
    }


def execute_create_pool_tx(
    client,
    publish_result: dict,
    params,
) -> dict:
    """
    TX 2: Create the bonding curve pool with first buy.
    """
    from pysui.sui.sui_txn.sync_transaction import SuiTransaction
    from pysui.sui.sui_types.scalars import SuiString, SuiU64, SuiU8, ObjectID

    coin_type        = publish_result["coin_type"]
    treasury_cap_id  = publish_result["treasury_cap_id"]
    coin_metadata_id = publish_result["coin_metadata_id"]

    first_buy_mist    = int(params.first_buy_sui * 1e9)
    target_raise_mist = int(params.target_raise_sui * 1e9)
    platform_fee_mist = int(first_buy_mist * 0.02)
    total_sui_mist    = first_buy_mist + platform_fee_mist

    txn = SuiTransaction(client=client)

    # Split SUI for payment (first buy + fee)
    [payment_coin] = txn.split_coin(
        coin=txn.gas,
        amounts=[total_sui_mist],
    )

    txn.move_call(
        target=f"{PACKAGE}::moonbags::create_and_lock_first_buy_with_fee",
        arguments=[
            ObjectID(CONFIG),
            ObjectID(STAKE_CFG),
            ObjectID(LOCK_CFG),
            ObjectID(treasury_cap_id),
            ObjectID(coin_metadata_id),
            ObjectID(SUI_META),
            payment_coin,
            ObjectID(CLOCK),
            SuiU64(platform_fee_mist),
            SuiU8(params.migrate_to),
            SuiU64(first_buy_mist),
            SuiU64(target_raise_mist),
            SuiString(params.name),
            SuiString(params.symbol.upper()),
            SuiString(params.image_url),
            SuiString(params.description),
            SuiString(params.twitter),
            SuiString(params.telegram),
            SuiString(params.website),
            SuiString(""),  # live_stream_url
        ],
        type_arguments=[coin_type, SUI_TYPE],
    )

    txn.set_gas_budget(200_000_000)

    result = client.execute(txn)
    if result.is_err():
        raise RuntimeError(f"Create pool TX failed: {result.result_string}")

    return result.result_data


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
    migrate_to:       int   = 1      # 1 = Turbos


# ── Dry run ───────────────────────────────────────────────────────────────────

async def dry_run(params: LaunchParams):
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  🚀 ODYSSEY LAUNCH — DRY RUN")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"  Name:         {params.name}")
    print(f"  Symbol:       ${params.symbol.upper()}")
    print(f"  First buy:    {params.first_buy_sui} SUI")
    print(f"  Target raise: {params.target_raise_sui} SUI")
    print(f"  Migrate to:   {'Turbos' if params.migrate_to == 1 else 'Cetus'}")
    print()

    est_tokens = tokens_out_estimate(int(params.first_buy_sui * 1e9))
    fee        = params.first_buy_sui * 0.02
    price      = starting_price_sui()
    total_cost = params.first_buy_sui + fee

    print(f"  📊 Est. tokens from first buy: {est_tokens:,.0f} ${params.symbol.upper()}")
    print(f"  💰 Starting price:             {price:.10f} SUI")
    print(f"  💸 2% platform fee:            {fee:.4f} SUI")
    print(f"  💳 Total SUI needed:           {total_cost:.4f} SUI + gas (~0.05 SUI)")
    print()

    # Test bytecode patching
    try:
        patched = patch_bytecode(params.symbol, params.name)
        sym_b = params.symbol.upper().encode()
        mod_b = params.symbol.lower().encode()
        ok = sym_b in patched and mod_b in patched and b"COIN_TEMPLATE" not in patched
        print(f"  ✅ Bytecode patch: {'OK' if ok else 'FAILED'}")
        print(f"     Size: {len(patched)} bytes")
        print(f"     Struct {params.symbol.upper()}: {'✓' if sym_b in patched else '✗'}")
        print(f"     Module {params.symbol.lower()}: {'✓' if mod_b in patched else '✗'}")
        print(f"     Template cleared:   {'✓' if b'COIN_TEMPLATE' not in patched else '✗'}")
    except Exception as e:
        print(f"  ❌ Bytecode patch: FAILED — {e}")
        return

    print()
    print("  TX 1: Publish coin package")
    print(f"         Coin type → 0x<PKG>::{params.symbol.lower()}::{params.symbol.upper()}")
    print("  TX 2: create_and_lock_first_buy_with_fee")
    print(f"         Pool on Odyssey · {est_tokens:,.0f} tokens locked for creator")
    print()
    print("  ℹ️  Set PRIVATE_KEY=suiprivk1... and remove --dry-run to execute")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")


# ── Live launch ───────────────────────────────────────────────────────────────

async def live_launch(params: LaunchParams):
    print(f"\n🚀 Launching ${params.symbol.upper()} on Odyssey...")

    # Load wallet
    client, kp, address = load_signer()
    print(f"   Wallet: {address}")

    # Check balance
    coins = await get_sui_coins(address)
    if not coins:
        raise RuntimeError("No SUI coins found in wallet")
    total_bal = sum(int(c["balance"]) for c in coins) / 1e9
    needed    = params.first_buy_sui * 1.02 + 0.1
    print(f"   Balance: {total_bal:.4f} SUI (need ~{needed:.4f})")
    if total_bal < needed:
        raise RuntimeError(f"Insufficient balance: {total_bal:.4f} SUI < {needed:.4f} SUI needed")

    # TX 1: Publish coin package
    print("\n📦 TX 1: Publishing coin package...")
    t0 = time.time()
    patched_bytes = patch_bytecode(params.symbol, params.name)
    print(f"   Bytecode patched: {len(patched_bytes)} bytes")

    tx1_data = execute_publish_tx(client, patched_bytes, address)
    publish  = extract_publish_result(tx1_data, params.symbol)

    print(f"   ✅ Published in {time.time()-t0:.1f}s")
    print(f"   Package:      {publish['package_id']}")
    print(f"   Coin type:    {publish['coin_type']}")
    print(f"   TreasuryCap:  {publish['treasury_cap_id']}")
    print(f"   TX:           {publish['digest']}")

    # TX 2: Create pool
    print("\n🏊 TX 2: Creating bonding curve pool...")
    t1 = time.time()

    tx2_data = execute_create_pool_tx(client, publish, params)
    digest2  = tx2_data.digest if hasattr(tx2_data, 'digest') else "unknown"

    # Find pool ID in object changes
    pool_id = None
    changes = tx2_data.object_changes if hasattr(tx2_data, 'object_changes') else []
    for c in changes:
        otype = str(c.object_type if hasattr(c, 'object_type') else c.get("objectType", ""))
        if "Pool" in otype and "moonbags" in otype:
            pool_id = str(c.object_id if hasattr(c, 'object_id') else c.get("objectId", ""))
            break

    est_tokens = tokens_out_estimate(int(params.first_buy_sui * 1e9))

    print(f"   ✅ Pool created in {time.time()-t1:.1f}s")
    print(f"   Pool ID: {pool_id or '(check explorer)'}")
    print(f"   TX:      {digest2}")

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  🎉 ${params.symbol.upper()} LAUNCHED SUCCESSFULLY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Name:       {params.name}
  Coin type:  {publish['coin_type']}
  Pool:       {pool_id or '(check explorer)'}
  Tokens:     ~{est_tokens:,.0f} ${params.symbol.upper()} (locked)
  View:       https://theodyssey.fun/bondingcurve/coins/{pool_id or ''}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    return {
        "coin_type": publish["coin_type"],
        "pool_id":   pool_id,
        "package":   publish["package_id"],
        "tx1":       publish["digest"],
        "tx2":       digest2,
    }


# ── Query pool ────────────────────────────────────────────────────────────────

async def query_pool(pool_id: str):
    print(f"\n📊 Pool state: {pool_id}")
    state = await get_pool_state(pool_id)
    print(f"   Price:     {state['price_sui']:.10f} SUI/token")
    print(f"   Raised:    {state['real_sui'] / 1e9:.4f} SUI")
    print(f"   Progress:  {state['progress']:.2f}%")
    print(f"   Graduated: {state['is_completed']}")
    if not state["is_completed"]:
        remaining = (state["threshold"] - state["real_sui"]) / 1e9
        print(f"   Remaining: {remaining:.2f} SUI until graduation")


# ── CLI ───────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Launch token on Odyssey 2.0 bonding curve")
    parser.add_argument("--name",        help="Token name (e.g. 'Moon Dog')")
    parser.add_argument("--ticker", "-t",help="Ticker symbol (e.g. MOON)")
    parser.add_argument("--description", default="")
    parser.add_argument("--image",       default="", help="Image URL")
    parser.add_argument("--twitter",     default="")
    parser.add_argument("--telegram",    default="")
    parser.add_argument("--website",     default="")
    parser.add_argument("--sui",    "-s",type=float, default=50.0,   help="First buy SUI")
    parser.add_argument("--target",      type=float, default=2000.0, help="Graduation target SUI")
    parser.add_argument("--migrate",     choices=["turbos"], default="turbos")
    parser.add_argument("--pool",        help="Query pool state by ID (no launch)")
    parser.add_argument("--dry-run",     action="store_true")
    args = parser.parse_args()

    if args.pool:
        await query_pool(args.pool)
        return

    if not args.name or not args.ticker:
        parser.error("--name and --ticker are required for launching")

    params = LaunchParams(
        name=args.name,
        symbol=args.ticker.upper().replace(" ", ""),
        description=args.description,
        image_url=args.image,
        twitter=args.twitter,
        telegram=args.telegram,
        website=args.website,
        first_buy_sui=args.sui,
        target_raise_sui=args.target,
        migrate_to=1,
    )

    if args.dry_run:
        await dry_run(params)
    else:
        await live_launch(params)


if __name__ == "__main__":
    asyncio.run(main())
