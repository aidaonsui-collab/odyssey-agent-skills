---
name: odyssey-token-launch
description: |
  Autonomous AI agent skill for launching tokens on the Odyssey 2.0 bonding curve launchpad.
  
  This skill enables AI agents to programmatically launch meme tokens on Sui blockchain with:
  - x402 micro-payment authentication (no manual approval required)
  - Bonding curve math with calibrated constants
  - Full transaction flow: publish → create_pool → register
  - Dry-run mode for simulation

  Use when: launching new tokens, managing token creation workflow, integrating with Odyssey backend.
license: MIT
metadata:
  version: "1.0.0"
  category: defi
  sources:
    - Odyssey 2.0 Contract (mainnet)
    - Sui Move programming language
    - x402 micro-payment protocol
invocation:
  pattern: "/odyssey-launch <token_name> [options]"
  example: "/odyssey-launch MyToken --ticker MINE --sui 50 --migrate cetus"
---

# Odyssey Token Launch

Autonomous token launch on Odyssey 2.0 bonding curve launchpad.

## Skill Structure

```
odyssey-token-launch/
├── SKILL.md                      # This file
├── scripts/
│   ├── launch_token.py           # Main launch workflow
│   ├── pay_invoice.py           # x402 payment handling
│   └── publish_coin.py          # Coin module publishing
├── references/
│   ├── bonding-curve-math.md    # Price calculations
│   ├── contract-api.md          # Contract addresses & functions
│   ├── x402-payment-flow.md     # Payment integration
│   └── sui-rpc-reference.md     # Sui RPC usage
└── templates/
    └── complete_launch.py        # Full implementation example
```

---

## Invocation

```
/odyssey-launch <token_name> --ticker <TICKER> --sui <AMOUNT> [options]

Required:
  token_name              Name of the token
  --ticker, -t            Ticker symbol (max 10 chars)
  --sui, -s               Initial SUI amount for first buy

Optional:
  --migrate               Migration target: cetus (default) or turbos
  --target                Target raise in SUI (default: 2000)
  --dry-run               Simulate without executing
  --image                 Image URL for token logo
  --twitter               Twitter URL
  --telegram              Telegram URL
  --website               Website URL
```

---

## Workflow

### Phase 1: Payment (x402)

```
1. GET /api/v1/payment/invoice
   └── Response: { invoiceId, amountSui, payTo, expiresAt }

2. Send SUI to payTo address
   └── Amount: amountSui
   └── Memo: invoiceId

3. POST /api/v1/payment/confirm
   └── Body: { invoiceId, txDigest }
   └── Response: { status: 'confirmed' }

4. Proceed to launch with payment proof
```

### Phase 2: Token Launch

```
1. Prepare launch parameters
   ├── name, ticker, description
   ├── first_buy_sui amount
   ├── migrate_to (0=Cetus, 1=Turbos)
   └── target_raise_sui

2. Call POST /api/v1/tokens/auto-create
   ├── Body: { name, symbol, description, ..., paymentInvoiceId, paymentTxDigest }
   └── Response: { packageId, treasuryCapId, tokenType, ptbInstructions }

3. Build and execute create_pool transaction
   ├── Use ptbInstructions from response
   └── Sign with agent wallet

4. Register token
   └── POST /api/v1/memecoins/create or /tokens/confirm
```

---

## Bonding Curve Constants

```python
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000                     # ~0.667 SUI in mist
TOKEN_DECIMALS = 6
```

### Price Table

| SUI Input | Tokens Received | % of Supply | Price per Token |
|-----------|------------------|-------------|-----------------|
| 1 SUI     | ~1.6M            | 50%         | ~0.0000006 SUI  |
| 10 SUI    | ~15.8M           | 91%         | ~0.0000006 SUI  |
| 50 SUI    | ~74.4M           | 98%         | ~0.0000007 SUI  |

---

## Contract Addresses (Mainnet)

| Contract          | Address                                                |
|-------------------|--------------------------------------------------------|
| Odyssey Package   | `0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da` |
| Module            | `moonbags`                                             |
| Configuration     | `0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f` |
| Stake Config      | `0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49` |
| Lock Config       | `0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006` |
| SUI Clock         | `0x0000000000000000000000000000000000000000000000000000000000000006` |

---

## Python Implementation

```python
import httpx
from dataclasses import dataclass

BACKEND_URL = "https://your-odyssey-backend.railway.app"

@dataclass
class LaunchParams:
    name: str
    ticker: str
    description: str = ""
    first_buy_sui: float = 50.0
    migrate_to: int = 0  # 0=Cetus, 1=Turbos
    target_raise_sui: float = 2000.0
    image_url: str = ""
    twitter: str = ""
    telegram: str = ""
    website: str = ""

def calculate_tokens(sui_amount: float) -> float:
    """Calculate tokens received for SUI input."""
    VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000
    VIRTUAL_SUI_START = 666_730_000
    TOKEN_DECIMALS = 6
    
    sui_mist = int(sui_amount * 1e9)
    tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
    return tokens_raw / (10 ** TOKEN_DECIMALS)

async def launch_token(params: LaunchParams, wallet, dry_run: bool = False):
    """Main launch workflow."""
    
    # Step 1: Get payment invoice
    invoice_resp = httpx.get(f"{BACKEND_URL}/api/v1/payment/invoice")
    invoice = invoice_resp.json()
    
    # Step 2: Agent sends payment (implement with pysui)
    payment_tx = build_payment_tx(wallet, invoice['payTo'], invoice['amountSui'], invoice['invoiceId'])
    payment_digest = execute_tx(payment_tx)
    
    # Step 3: Confirm payment
    confirm_resp = httpx.post(
        f"{BACKEND_URL}/api/v1/payment/confirm",
        json={"invoiceId": invoice["invoiceId"], "txDigest": payment_digest}
    )
    assert confirm_resp.json()["status"] == "confirmed"
    
    # Step 4: Auto-create token
    create_resp = httpx.post(
        f"{BACKEND_URL}/api/v1/tokens/auto-create",
        json={
            "name": params.name,
            "symbol": params.ticker,
            "description": params.description,
            "initialSuiAmount": params.first_buy_sui,
            "migrateTo": params.migrate_to,
            "creator": wallet.address,
            "paymentInvoiceId": invoice["invoiceId"],
            "paymentTxDigest": payment_digest,
        }
    )
    result = create_resp.json()
    
    # Step 5: Build and execute create_pool
    if not dry_run:
        pool_result = execute_create_pool(wallet, result)
        return pool_result
    
    return {"dry_run": True, "expected_tokens": calculate_tokens(params.first_buy_sui)}
```

---

## Error Handling

| Error Code | Meaning                          | Resolution                        |
|------------|----------------------------------|-----------------------------------|
| 400        | Invalid parameters               | Check name, ticker, amounts       |
| 402        | Payment required                 | Complete x402 payment flow        |
| 402        | Payment not confirmed            | Wait and retry /payment/status    |
| 500        | Compilation/publish failed       | Check Move module syntax          |

---

## Quality Gates

- [ ] Validate ticker (max 10 chars, alphanumeric)
- [ ] Validate first_buy_sui >= 1
- [ ] Validate target_raise_sui >= 2000
- [ ] Verify payment confirmed before auto-create
- [ ] Check pool creation success
- [ ] Log transaction digest for audit
- [ ] Test on testnet before mainnet

---

## References

See `references/` directory for:
- `bonding-curve-math.md` - Detailed price calculations
- `contract-api.md` - Full contract API reference
- `x402-payment-flow.md` - Payment integration guide
- `sui-rpc-reference.md` - Sui RPC usage

See `scripts/` directory for:
- `launch_token.py` - Complete launch workflow
- `pay_invoice.py` - Payment handling
- `publish_coin.py` - Direct coin publishing
