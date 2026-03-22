# Odyssey Agent Skills

AI agent skills for launching and trading tokens on the **Odyssey 2.0** bonding curve launchpad on **Sui blockchain**.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Set Wallet

```bash
# Option 1: Just set address (for read-only operations)
export WALLET_ADDRESS=0x_your_wallet_address_here

# Option 2: Full credentials (for signing transactions)
export WALLET_ADDRESS=0x_your_wallet_address_here
export WALLET_MNEMONIC="word1 word2 word3 ... word24"

# Network (default: mainnet)
export SUI_NETWORK=https://fullnode.mainnet.sui.io:443
# For testnet:
# export SUI_NETWORK=https://fullnode.testnet.sui.io:443
```

### 3. CLI Usage

```bash
# Calculate price
python -m odyssey_agent_skills price --sui 10

# Launch a token (dry run)
python -m odyssey_agent_skills launch --name "My Token" --ticker MINE --sui 50 --dry-run

# Buy tokens (dry run)
python -m odyssey_agent_skills buy --pool 0x... --token 0x... --sui 10 --dry-run

# Sell tokens (dry run)
python -m odyssey_agent_skills sell --pool 0x... --token 0x... --amount 1000 --dry-run
```

### 4. x402 Payment (Auto-Create)

Auto-create requires x402 micro-payment (0.05 SUI) to prevent spam:

```bash
# 1. Get payment invoice
curl https://your-backend.railway.app/api/v1/payment/invoice

# 2. Send SUI to the payTo address with invoiceId as memo

# 3. Confirm payment
curl -X POST https://your-backend.railway.app/api/v1/payment/confirm \
  -d '{"invoiceId": "inv_xxx", "txDigest": "your_tx_digest"}'

# 4. Now call auto-create with payment proof
curl -X POST https://your-backend.railway.app/api/v1/tokens/auto-create \
  -d '{"name": "MyToken", ..., "paymentInvoiceId": "inv_xxx", "paymentTxDigest": "your_tx_digest"}'
```

See `SKILL.md` for full Python implementation.

### 4. Run Example

```bash
python examples/launch_and_first_buy.py
python examples/sell_after_launch.py
```

## Skills

### [sui-token-launch](skills/sui-token-launch) - Token Launch

Launch new tokens on Odyssey bonding curves.

```python
from sui_token_launch.launcher import OdysseyLauncher, LaunchParams

launcher = OdysseyLauncher()

params = LaunchParams(
    token_name="My Token",
    ticker="MINE",
    description="A new token",
    first_buy_sui=50.0,
    migrate_to=0,  # 0=Cetus, 1=Turbos
    target_raise_sui=2000.0
)

result = launcher.launch_token(params, dry_run=True)
print(f"Tokens: {result.tokens_received}")
```

### [sui-bonding-curve-trade](skills/sui-bonding-curve-trade) - Trading

Buy and sell tokens on Odyssey bonding curves.

```python
from sui_bonding_curve_trade.trader import OdysseyTrader

trader = OdysseyTrader()

# Buy tokens
result = trader.buy(
    pool_id="0x...",
    token_type="0x...::COIN::COIN",
    sui_amount=10.0
)
print(f"Tokens: {result.tokens_display}")

# Sell tokens
result = trader.sell(
    pool_id="0x...",
    token_type="0x...::COIN::COIN",
    token_amount=1000.0
)
print(f"SUI: {result.sui_amount}")
```

### [onlyfence-guardrails](skills/onlyfence-guardrails) - Security

Safety guardrails for autonomous trading.

```python
from onlyfence_guardrails.guardrails import OnlyFenceGuardrails

guardrails = OnlyFenceGuardrails()

# Check trade
result = guardrails.check_trade(
    token_address="0x...",
    amount_usd=50.0
)
if result.allowed:
    # Execute trade
    pass
else:
    print(f"Blocked: {result.reason}")
```

## Bonding Curve Constants

```python
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000                     # ~0.667 SUI
TOKEN_DECIMALS = 6
```

### Price Table

| SUI Input | Tokens Received | % of Supply | Price per Token |
|-----------|-----------------|-------------|----------------|
| 1 SUI | ~1.6M | 50% | ~0.0000006 SUI |
| 10 SUI | ~15.8M | 91% | ~0.0000006 SUI |
| 50 SUI | ~74.4M | 98% | ~0.0000007 SUI |

## Contract Addresses (Mainnet)

| Contract | Address |
|----------|---------|
| Odyssey Package | `0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da` |
| Module | `moonbags` |
| Configuration | `0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f` |
| Stake Config | `0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49` |
| Lock Config | `0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006` |

## Agent Integration

### Tool Schemas

Ready for OpenAI function calling, LangChain tools, CrewAI, etc.

```json
{
  "name": "odyssey_buy_token",
  "parameters": {
    "pool_id": "string",
    "token_type": "string",
    "sui_amount": "number"
  }
}
```

### LangChain Example

```python
from langchain_core.tools import tool

@tool
def odyssey_buy_token(pool_id: str, sui_amount: float):
    """Buy tokens from Odyssey bonding curve."""
    # ... implementation
```

### LangGraph Example

```python
from langgraph.prebuilt import create_react_agent

agent = create_react_agent(
    model,
    tools=odyssey_tools,
    state_modifier="You are a Sui blockchain trading agent."
)
```

## Project Structure

```
odyssey-agent-skills/
├── odyssey_agent_skills/      # CLI package
│   ├── __init__.py
│   └── __main__.py            # CLI entry point
├── skills/
│   ├── sui-token-launch/
│   │   ├── launcher.py        # Main implementation
│   │   ├── __init__.py
│   │   └── SKILL.md
│   ├── sui-bonding-curve-trade/
│   │   ├── trader.py          # Main implementation
│   │   ├── tests/            # Unit tests
│   │   ├── __init__.py
│   │   └── SKILL.md
│   └── onlyfence-guardrails/
│       ├── guardrails.py      # Main implementation
│       ├── tests/             # Guardrail tests
│       ├── __init__.py
│       └── SKILL.md
├── examples/
│   ├── launch_and_first_buy.py
│   ├── launch_buy_demo.py     # Full demo with guardrails
│   ├── sell_after_launch.py   # P&L scenarios
│   └── langchain_example.py
├── requirements.txt
├── pyproject.toml
└── README.md
```

## Running Tests

```bash
cd skills/sui-bonding-curve-trade
python -m pytest tests/ -v
```

## Current Status

- [x] Token launch (Python)
- [x] Trading (Python)
- [x] Guardrails (Python)
- [x] Tool schemas
- [x] Unit tests
- [x] Example scripts
- [x] CLI interface
- [ ] TypeScript/JavaScript implementations
- [ ] Real wallet integration (pysui)
- [ ] Live testnet deployment

## Dependencies

- pysui >= 0.50.0
- pydantic >= 2.0
- aiohttp >= 3.9.0

## License

MIT
