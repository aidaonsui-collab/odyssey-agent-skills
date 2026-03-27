# Odyssey Contract API Reference

## Live Mainnet Addresses

| Contract | Address |
|---|---|
| **Package (v7)** | `0xf1c7fe9b6ad3c243f794d41e87fab502883d5fc27e005d72e94fe64bbf08c69b` |
| **Module** | `moonbags` |
| **Configuration** | `0xfb774b5c4902d7d39e899388f520db0e2b1a6dca72687803b894d7d67eca9326` |
| **Stake Config** | `0x312216a4b80aa2665be3539667ef3749fafb0bde8c8ff529867ca0f0dc13bc18` |
| **Lock Config** | `0x7b3f064b45911affde459327ba394f2aa8782539d9b988c4986ee71c5bd34059` |
| **AIDA Token** | `0xcee208b8ae33196244b389e61ffd1202e7a1ae06c8ec210d33402ff649038892::aida::AIDA` |
| **SUI Clock** | `0x0000000000000000000000000000000000000000000000000000000000000006` |

> ⚠️ Token creation is **fully on-chain via PTB** — no backend required.
> The backend API (`/api/v1/tokens/create`) is a demo stub and does NOT execute real transactions.

---

## Bonding Curve Constants (on-chain)

```
VIRTUAL_TOKEN_RESERVES = 2_131_961_013_243_971   # raw (6 decimals)
VIRTUAL_SUI_RESERVES   = 2_001_287_378_847        # raw (9 decimals = ~2001 SUI)
GRADUATION_THRESHOLD   = 2_000_000_000_000_000    # 2000 SUI in MIST
TOKEN_DECIMALS         = 6
PLATFORM_FEE_BPS       = 200                      # 2%
```

### Price formula

```python
# Current price in SUI per token
price_sui = virtual_sui_reserves / 1e9 / (virtual_token_reserves / 1e6)

# Tokens out for SUI in (buy)
def tokens_out(sui_in_mist, v_sui, v_token):
    return (sui_in_mist * v_token) / (v_sui + sui_in_mist)

# SUI out for tokens in (sell)  
def sui_out(token_in_raw, v_sui, v_token):
    return (token_in_raw * v_sui) / (v_token + token_in_raw)
```

---

## Token Launch — Full On-chain Flow

Launching a token requires **two sequential transactions**:

### TX 1: Publish coin package

Use the bytecode patching approach — patch the `coin_template` bytecode with the actual ticker, then publish:

```python
# The base64 bytecode template (from contracts.ts)
COIN_BYTECODE_B64 = "oRzrCwYAAAAKAQAMAgweAyocBEYIBU5RB58BqwEIygJgBqoDGwrFAwUMygMtAAcBDAIGAg8CEAIRAAACAAECBwEAAAIBDAEAAQIDDAEAAQQEAgAFBQcAAAoAAQABCwEEAQACCAYHAQIDDQsBAQwEDggJAAEDAgUDCgMMAggABwgEAAILAgEIAAsDAQgAAQgFAQsBAQkAAQgABwkAAgoCCgIKAgsBAQgFBwgEAgsDAQkACwIBCQABBggEAQUBCwIBCAACCQAFAQsDAQgADUNPSU5fVEVNUExBVEUMQ29pbk1ldGFkYXRhBk9wdGlvbgtUcmVhc3VyeUNhcAlUeENvbnRleHQDVXJsBGNvaW4NY29pbl90ZW1wbGF0ZQ9jcmVhdGVfY3VycmVuY3kLZHVtbXlfZmllbGQEaW5pdARub25lBm9wdGlvbg9wdWJsaWNfdHJhbnNmZXIGc2VuZGVyCHRyYW5zZmVyCnR4X2NvbnRleHQDdXJsV6zO2JBHJ3Lh42Zr3Y84+I3JoNOWqP5B/vpOkbfvtSIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACCgIGBVRva2VuCgILClRva2VuIE5hbWUKAgEAAAIBCQEAAAAAAhULADEGBwAHAQcCOAAKATgBDAIMAwsCCgEuEQQ4AgsDCwEuEQQ4AwIA"

def patch_bytecode(b64_template: str, symbol: str, name: str) -> str:
    """Patch coin_template bytecode with actual ticker symbol and name."""
    import base64
    data = bytearray(base64.b64decode(b64_template))
    sym_upper = symbol.upper()
    sym_lower = symbol.lower()

    def find_len_prefixed(data, s):
        target = bytes([len(s)]) + s.encode()
        pos = bytes(data).find(target)
        if pos == -1: raise ValueError(f"'{s}' not found in bytecode")
        return pos, target

    patches = []
    for placeholder, replacement in [
        ('COIN_TEMPLATE', sym_upper),
        ('coin_template', sym_lower),
        ('Token',         sym_upper),
        ('Token Name',    name),
    ]:
        pos, old = find_len_prefixed(data, placeholder)
        new = bytes([len(replacement)]) + replacement.encode()
        patches.append((pos, len(old), new))

    for start, old_len, new_bytes in sorted(patches, key=lambda x: -x[0]):
        data[start:start+old_len] = new_bytes

    return base64.b64encode(bytes(data)).decode()
```

```python
# Build publish PTB (using pysui or httpx direct RPC)
from pysui.sui.sui_txn import SyncTransaction

def build_publish_tx(symbol: str, name: str) -> SyncTransaction:
    patched_b64 = patch_bytecode(COIN_BYTECODE_B64, symbol, name)
    module_bytes = list(base64.b64decode(patched_b64))

    txn = SyncTransaction(client=sui_client)
    upgrade_cap = txn.publish(
        project_path=None,
        compiled_modules=[module_bytes],
        dependencies=[
            "0x0000000000000000000000000000000000000000000000000000000000000001",
            "0x0000000000000000000000000000000000000000000000000000000000000002",
        ]
    )
    txn.transfer_objects(transfers=[upgrade_cap], recipient=sender_address)
    return txn
```

After TX 1 executes, extract from `objectChanges`:
- `packageId` — the published package address
- `TreasuryCap` object ID
- `CoinMetadata` object ID
- `coinType` = `{packageId}::{symbol.lower()}::{SYMBOL}`

---

### TX 2: Create pool

```python
PACKAGE    = "0xf1c7fe9b6ad3c243f794d41e87fab502883d5fc27e005d72e94fe64bbf08c69b"
CONFIG     = "0xfb774b5c4902d7d39e899388f520db0e2b1a6dca72687803b894d7d67eca9326"
STAKE_CFG  = "0x312216a4b80aa2665be3539667ef3749fafb0bde8c8ff529867ca0f0dc13bc18"
LOCK_CFG   = "0x7b3f064b45911affde459327ba394f2aa8782539d9b988c4986ee71c5bd34059"
CLOCK      = "0x0000000000000000000000000000000000000000000000000000000000000006"
SUI_META   = "0x9258181f5ceac8dbffb7030890243caed69a9599d2886d957a9cb7656af3bdb3"

def build_create_pool_tx(
    coin_type: str,         # e.g. "0xABC::hope::HOPE"
    treasury_cap_id: str,
    coin_metadata_id: str,
    first_buy_sui: float,   # SUI for initial buy
    target_raise_sui: float = 2000.0,
    migrate_to: int = 1,    # 1=Turbos (only supported currently)
    name: str = "",
    symbol: str = "",
    image_url: str = "",
    description: str = "",
    twitter: str = "",
    telegram: str = "",
    website: str = "",
) -> dict:
    """Returns a PTB-compatible dict for create_and_lock_first_buy_with_fee."""

    first_buy_mist   = int(first_buy_sui * 1e9)
    target_raise_mist = int(target_raise_sui * 1e9)
    platform_fee_mist = int(first_buy_mist * 0.02)  # 2% platform fee

    return {
        "target": f"{PACKAGE}::moonbags::create_and_lock_first_buy_with_fee",
        "typeArguments": [coin_type, "0x2::sui::SUI"],
        "arguments": {
            "config":          CONFIG,
            "stake_config":    STAKE_CFG,
            "lock_config":     LOCK_CFG,
            "treasury_cap":    treasury_cap_id,
            "coin_metadata":   coin_metadata_id,
            "sui_metadata":    SUI_META,
            "clock":           CLOCK,
            "fee":             platform_fee_mist,
            "migrate_to":      migrate_to,
            "first_buy":       first_buy_mist,
            "target_raise":    target_raise_mist,
            "name":            name,
            "symbol":          symbol,
            "image_url":       image_url,
            "description":     description,
            "twitter":         twitter,
            "telegram":        telegram,
            "website":         website,
            "live_stream_url": "",
        }
    }
```

---

## Trading

```python
# BUY
{
    "target": f"{PACKAGE}::moonbags::buy",
    "typeArguments": [coin_type, "0x2::sui::SUI"],
    "arguments": {
        "pool":    pool_id,
        "payment": sui_coin,        # split from gas
        "min_out": min_tokens_raw,  # slippage protection
    }
}

# SELL
{
    "target": f"{PACKAGE}::moonbags::sell",
    "typeArguments": [coin_type, "0x2::sui::SUI"],
    "arguments": {
        "pool":      pool_id,
        "token_in":  token_coin_id,
        "min_quote": min_sui_raw,   # slippage protection
    }
}
```

---

## Fee Structure

| Fee | Amount | Distribution |
|---|---|---|
| Trading fee | 2% per trade | 30% stakers · 40% creator · 30% platform |
| Platform stake fee | 0.01% | AIDA stakers |
| Creation fee | 0.05 SUI | Platform |

---

## REST API (read-only helpers)

The backend at `https://theodyssey-backend1-production.up.railway.app` provides **read-only** endpoints for querying state. It does **not** execute transactions — all writes go directly on-chain.

```
GET  /health                          # Health check
GET  /api/v1/config                   # Platform config
GET  /api/v1/tokens/:address/stats    # Token stats (on-chain)
GET  /api/v1/memecoins/all            # All tokens
GET  /api/v1/memecoins/trending       # Trending tokens
POST /api/v1/auth/register            # Register for API key
```
