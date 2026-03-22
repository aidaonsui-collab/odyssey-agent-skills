# Odyssey Agent Skills

AI agent skills for launching and trading tokens on the **Odyssey 2.0** bonding curve launchpad on **Sui blockchain**.

## Skills

| Skill | Description |
|-------|-------------|
| [odyssey-token-launch](skills/odyssey-token-launch) | Launch tokens with x402 payment |
| [odyssey-bonding-trade](skills/odyssey-bonding-trade) | Buy/sell on bonding curves |
| [onlyfence-guardrails](skills/onlyfence-guardrails) | Safety guardrails for trading |

## Quick Start

### 1. Install Dependencies

```bash
pip install pysui httpx pydantic
```

### 2. Set Environment

```bash
export ODYSSEY_BACKEND_URL=https://your-backend.railway.app
export WALLET_ADDRESS=0x_your_wallet
export WALLET_MNEMONIC="word1 word2 ... word24"
```

### 3. Launch a Token

```bash
# Using the script
python -m odyssey_token_launch.scripts.launch_token \
  --name "MyToken" \
  --ticker MINE \
  --sui 50 \
  --migrate cetus

# Or use the template directly
python complete_launch.py
```

## x402 Payment (Auto-Create)

The `POST /api/v1/tokens/auto-create` endpoint requires x402 micro-payment:

```bash
# 1. Get invoice
curl https://backend.railway.app/api/v1/payment/invoice

# 2. Send SUI to payTo address with memo: invoiceId

# 3. Confirm payment
curl -X POST https://backend.railway.app/api/v1/payment/confirm \
  -d '{"invoiceId": "inv_xxx", "txDigest": "your_tx"}'

# 4. Launch token
curl -X POST https://backend.railway.app/api/v1/tokens/auto-create \
  -d '{"name": "MyToken", ..., "paymentInvoiceId": "inv_xxx", "paymentTxDigest": "your_tx"}'
```

## Bonding Curve Constants

```python
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000                     # ~0.667 SUI
TOKEN_DECIMALS = 6
```

### Price Table

| SUI Input | Tokens Received | % of Supply |
|-----------|-----------------|--------------|
| 1 SUI     | ~1.6M           | 50%          |
| 10 SUI    | ~15.8M          | 91%          |
| 50 SUI    | ~74.4M          | 98%          |

## Contract Addresses (Mainnet)

| Contract          | Address |
|-------------------|---------|
| Odyssey Package   | `0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da` |
| Module            | `moonbags` |

## Status

- ✅ Token launch (Python + x402)
- ✅ Trading (Python)
- ✅ Guardrails (Python)
- ✅ Tool schemas
- ✅ Scripts & templates
- ✅ References
- ⏳ Real wallet integration (pysui)

## License

MIT
