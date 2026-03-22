# sui-token-launch

Autonomous AI agent skill for launching tokens on the Odyssey 2.0 bonding curve launchpad.

## Installation

```bash
pip install pysui
```

## Python Implementation

```python
from pysui import SuiClient, SuiConfig
from pysui.sui_txn import Transaction
from pysui.sui_types import (
    SuiAddress, ObjectDigest, SequenceNumber
)
import json

# Configuration
ODYSSEY_PKG = "0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da"
MODULE = "moonbags"
CONFIG_OBJ = "0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f"
STAKE_CONFIG = "0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49"
LOCK_CONFIG = "0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006"
SUI_CLOCK = "0x0000000000000000000000000000000000000000000000000000000000000006"
POOL_FEE = 10_000_000  # 0.01 SUI in mist

# Bonding curve constants (calibrated to Moonbags)
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000  # ~0.667 SUI in mist
TOKEN_DECIMALS = 6

class OdysseyLauncher:
    def __init__(self, config_path: str = None):
        """Initialize Sui client."""
        if config_path:
            self.client = SuiClient(SuiConfig.from_yaml(config_path))
        else:
            self.client = SuiClient(SuiConfig.default())
        self.address = self.client.current_account.address
    
    def calculate_tokens(self, sui_amount: float) -> int:
        """Calculate tokens received for SUI input."""
        sui_mist = int(sui_amount * 1e9)
        tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
        return tokens_raw // (10 ** TOKEN_DECIMALS)
    
    def publish_coin(self, bytecode_path: str) -> dict:
        """Publish coin module and return package ID."""
        with open(bytecode_path, 'rb') as f:
            modules = [list(f.read())]
        
        tx = (
            Transaction()
            .publish(modules)
            .result()
        )
        
        # Find published package
        for obj in tx.created:
            if "package" in str(obj).lower():
                return {"package_id": obj.object_id}
        
        raise ValueError("Package ID not found in transaction")
    
    def create_pool(
        self,
        package_id: str,
        treasury_cap_id: str,
        metadata_id: str,
        first_buy_sui: float,
        migrate_to: int,  # 0=Cetus, 1=Turbos
        target_raise_sui: float,
        token_name: str,
        ticker: str,
        description: str,
        image_url: str = "",
        twitter: str = "",
        telegram: str = "",
        website: str = ""
    ) -> dict:
        """Create bonding curve pool."""
        first_buy_mist = int(first_buy_sui * 1e9)
        target_raise_mist = int(target_raise_sui * 1e9)
        
        tx = Transaction()
        
        # Split coins for first buy and fee
        coin = tx.split_coin(tx.gas(), [first_buy_mist + POOL_FEE])
        fee = tx.split_coin(coin, [POOL_FEE])
        first_buy = tx.split_coin(coin, [first_buy_mist])
        
        # Create pool
        tx.move_call(
            target=f"{ODYSSEY_PKG}::{MODULE}::create_and_lock_first_buy_with_fee",
            type_arguments=[f"{package_id}::coin_template::COIN_TEMPLATE"],
            arguments=[
                CONFIG_OBJ,
                STAKE_CONFIG,
                LOCK_CONFIG,
                treasury_cap_id,
                fee,
                migrate_to,
                first_buy,
                0,  # some arg
                b"",  # some arg
                target_raise_mist,
                SUI_CLOCK,
                token_name,
                ticker.upper(),
                image_url,
                description,
                twitter,
                telegram,
                website,
            ]
        )
        
        result = tx.execute(self.client)
        
        if result.effects.status.status != "success":
            raise ValueError(f"Pool creation failed: {result.effects.status.error}")
        
        # Extract pool ID from events
        pool_id = None
        for event in result.events:
            if "pool" in str(event.type).lower():
                pool_id = event.parsed_json.get("pool_id")
                break
        
        return {
            "pool_id": pool_id,
            "digest": result.digest,
            "first_buy_sui": first_buy_sui,
            "tokens_received": self.calculate_tokens(first_buy_sui)
        }

# Usage Example
if __name__ == "__main__":
    launcher = OdysseyLauncher()
    
    # Publish coin module (pre-compiled bytecode)
    pub_result = launcher.publish_coin("./coin_bytecode.module")
    print(f"Published: {pub_result['package_id']}")
    
    # Create pool
    pool = launcher.create_pool(
        package_id=pub_result["package_id"],
        treasury_cap_id="<treasury_cap_id>",
        metadata_id="<metadata_id>",
        first_buy_sui=50.0,
        migrate_to=0,  # Cetus
        target_raise_sui=2000.0,
        token_name="Test Token",
        ticker="TEST",
        description="A test token on Odyssey"
    )
    print(f"Pool created: {pool}")
```

## Tool Schema (for Agent Frameworks)

```json
{
  "name": "odyssey_launch_token",
  "description": "Launch a new token on Odyssey 2.0 bonding curve launchpad",
  "parameters": {
    "type": "object",
    "properties": {
      "token_name": {"type": "string", "description": "Name of the token"},
      "ticker": {"type": "string", "description": "Ticker symbol (max 10 chars)"},
      "description": {"type": "string", "description": "Token description"},
      "first_buy_sui": {"type": "number", "description": "Initial SUI to contribute"},
      "migrate_to": {"type": "integer", "enum": [0, 1], "description": "0=Cetus, 1=Turbos"},
      "target_raise_sui": {"type": "number", "description": "Target raise amount (min 2000)"},
      "twitter": {"type": "string", "description": "Twitter URL (optional)"},
      "telegram": {"type": "string", "description": "Telegram URL (optional)"},
      "website": {"type": "string", "description": "Website URL (optional)"},
      "image_url": {"type": "string", "description": "Token logo URL (optional)"}
    },
    "required": ["token_name", "ticker", "description", "first_buy_sui", "migrate_to", "target_raise_sui"]
  }
}
```

## Transaction Flow

```
1. Publish Coin Module
   └── Transaction: publish(coin_bytecode)
       └── Result: package_id, TreasuryCap

2. Create Pool
   └── Transaction: move_call(create_and_lock_first_buy_with_fee)
       ├── Arguments: config, treasury_cap, fee, first_buy, migrate_to, target_raise
       └── Result: pool_id, events

3. Register (Backend)
   └── POST /memecoins/create
       └── Body: name, ticker, desc, creator, coinAddress
```

## x402 Payment (Auto-Create Endpoint)

The `POST /api/v1/tokens/auto-create` endpoint requires x402 micro-payment to prevent spam.

### Payment Flow

```
1. GET /api/v1/payment/invoice
   └── Returns: invoiceId, amountSui, payTo address

2. Agent sends SUI to payTo address
   └── Transfer: exact amountSUI to payTo
   └── Memo: invoiceId (for tracking)

3. POST /api/v1/payment/confirm
   └── Body: { invoiceId, txDigest }
   └── Verifies payment on-chain

4. POST /api/v1/tokens/auto-create
   └── Body: { ..., paymentInvoiceId, paymentTxDigest }
   └── Executes if payment verified
```

### x402 Payment Example

```python
import httpx
from pysui import SuiClient, SuiConfig
from pysui.keypair import Keypair

BACKEND_URL = "https://your-odyssey-backend.railway.app"

async def launch_with_payment(
    wallet: Keypair,
    token_name: str,
    ticker: str,
    description: str,
    first_buy_sui: float
) -> dict:
    """Launch token with x402 payment."""
    client = SuiClient(SuiConfig.default())

    # Step 1: Get payment invoice
    invoice_resp = httpx.get(f"{BACKEND_URL}/api/v1/payment/invoice")
    invoice = invoice_resp.json()
    print(f"Invoice: {invoice['invoiceId']} for {invoice['amountSui']} SUI")

    # Step 2: Send payment (SUI transfer to backend wallet)
    # In production, use pysui to send SUI to invoice['payTo']
    payment_tx = (
        Transaction()
        .split_coin(coin, [int(invoice['amountSui'] * 1e9)])
        .transfer(recipient, invoice['payTo'])
    )
    # Sign and execute...
    payment_digest = "your_payment_tx_digest"

    # Step 3: Confirm payment with backend
    confirm_resp = httpx.post(
        f"{BACKEND_URL}/api/v1/payment/confirm",
        json={"invoiceId": invoice["invoiceId"], "txDigest": payment_digest}
    )
    confirm = confirm_resp.json()
    print(f"Payment status: {confirm['status']}")

    # Step 4: Now call auto-create with payment proof
    auto_create_resp = httpx.post(
        f"{BACKEND_URL}/api/v1/tokens/auto-create",
        json={
            "name": token_name,
            "symbol": ticker,
            "description": description,
            "initialSuiAmount": first_buy_sui,
            "creator": wallet.address(),
            "paymentInvoiceId": invoice["invoiceId"],
            "paymentTxDigest": payment_digest,
        }
    )
    return auto_create_resp.json()

# Or via Python class (OdysseyLauncher with payment)
from sui_token_launch.launcher import OdysseyLauncher, LaunchParams

launcher = OdysseyLauncher()

# Get invoice and pay
invoice = launcher.get_payment_invoice()  # GET /payment/invoice
launcher.pay_invoice(invoice, amount_sui=0.05)  # Send SUI

# Auto-create with payment
result = launcher.launch_token(params, payment_invoice_id=invoice["invoiceId"])
```

### Payment Configuration (Backend)

```python
# In backend/index.js
PAYMENT_CONFIG = {
    ENABLED: True,
    PRICE_SUI: 0.05,  # 0.05 SUI per auto-create
    PAY_TO_ADDRESS: '0x13ced8aca378f70af8244d1c6a3d8a9564ad1032028ebbbee65f5c3a22d12733',
    PAYMENT_TIMEOUT_MS: 5 * 60 * 1000,  # 5 minutes
}

# Environment variables:
# X402_ENABLED=true
# X402_PRICE_SUI=0.05
# X402_PAY_TO=0x_your_payment_wallet
```

### Error Responses

```json
// 402 Payment Required
{
  "error": "Payment required",
  "paymentInfo": {
    "priceSui": 0.05,
    "payTo": "0x13ced8...",
    "invoiceEndpoint": "GET /api/v1/payment/invoice"
  }
}

// 402 Payment Not Confirmed
{
  "error": "Payment not confirmed",
  "status": "pending",
  "checkEndpoint": "/api/v1/payment/status/inv_xxx"
}
```

### Disabling x402 (Development)

```bash
# In Railway environment variables:
X402_ENABLED=false
```
