# x402 Payment Flow

## Overview

Odyssey uses x402 micro-payments for the auto-create endpoint to enable fully autonomous token launches without manual approval.

## Configuration

```python
PAYMENT_CONFIG = {
    "enabled": True,
    "price_sui": 0.05,  # 0.05 SUI per publish
    "pay_to_address": "0x13ced8aca378f70af8244d1c6a3d8a9564ad1032028ebbbee65f5c3a22d12733",
    "timeout_ms": 5 * 60 * 1000,  # 5 minutes
}
```

## Payment Endpoints

### 1. GET /api/v1/payment/invoice

Generate a payment invoice.

**Request:**
```
GET /api/v1/payment/invoice
```

**Response:**
```json
{
  "invoiceId": "inv_1742612345678_abc123",
  "amountSui": 0.05,
  "payTo": "0x13ced8aca378f70af8244d1c6a3d8a9564ad1032028ebbbee65f5c3a22d12733",
  "expiresAt": 1742612645678,
  "instructions": "Send exactly 0.05 SUI to 0x13ced... with memo: inv_1742612345678_abc123",
  "statusUrl": "/api/v1/payment/status/inv_1742612345678_abc123"
}
```

### 2. GET /api/v1/payment/status/:invoiceId

Check payment status.

**Request:**
```
GET /api/v1/payment/status/inv_1742612345678_abc123
```

**Response (pending):**
```json
{
  "invoiceId": "inv_1742612345678_abc123",
  "status": "pending",
  "message": "Payment not yet confirmed. Send SUI and wait for confirmation.",
  "amountSui": 0.05,
  "payTo": "0x13ced8aca378f70af8244d1c6a3d8a9564ad1032028ebbbee65f5c3a22d12733"
}
```

**Response (confirmed):**
```json
{
  "invoiceId": "inv_1742612345678_abc123",
  "status": "confirmed",
  "txDigest": "4xDhZGCMhH6B1eZoPGhKJijJ3n1iKG5vFpL5r3L9mWZtF",
  "confirmedAt": 1742612545000
}
```

### 3. POST /api/v1/payment/confirm

Confirm payment with transaction digest.

**Request:**
```json
{
  "invoiceId": "inv_1742612345678_abc123",
  "txDigest": "4xDhZGCMhH6B1eZoPGhKJijJ3n1iKG5vFpL5r3L9mWZtF"
}
```

**Response:**
```json
{
  "success": true,
  "status": "confirmed",
  "message": "Payment verified on-chain"
}
```

### 4. POST /api/v1/tokens/auto-create

Launch token with payment proof.

**Request:**
```json
{
  "name": "MyToken",
  "symbol": "MINE",
  "description": "A test token",
  "initialSuiAmount": 50,
  "migrateTo": 0,
  "creator": "0x_agent_wallet",
  "paymentInvoiceId": "inv_1742612345678_abc123",
  "paymentTxDigest": "4xDhZGCMhH6B1eZoPGhKJijJ3n1iKG5vFpL5r3L9mWZtF"
}
```

---

## Complete Python Implementation

```python
import httpx
from pysui import SuiClient, SuiConfig
from pysui.sui_txn import Transaction

BACKEND_URL = "https://your-odyssey-backend.railway.app"

async def pay_and_launch(
    client: SuiClient,
    wallet_address: str,
    token_name: str,
    ticker: str,
    first_buy_sui: float
):
    """Complete x402 payment + token launch workflow."""
    
    # Step 1: Get invoice
    invoice_resp = httpx.get(f"{BACKEND_URL}/api/v1/payment/invoice")
    invoice = invoice_resp.json()
    print(f"Invoice: {invoice['invoiceId']} for {invoice['amountSui']} SUI")
    
    # Step 2: Send SUI payment
    # Get SUI coins from wallet
    coins = client.get_coins(wallet_address, "0x2::sui::SUI")
    
    # Build transfer transaction
    tx = (
        Transaction()
        .split_coin(coins[0], [int(invoice['amountSui'] * 1e9)])
        .transfer(tx.pure.address(invoice['payTo']), invoice['invoiceId'])
    )
    
    # Sign and execute
    result = client.sign_and_execute(tx, wallet=wallet_address)
    payment_digest = result.digest
    print(f"Payment tx: {payment_digest}")
    
    # Step 3: Confirm payment
    httpx.post(
        f"{BACKEND_URL}/api/v1/payment/confirm",
        json={
            "invoiceId": invoice["invoiceId"],
            "txDigest": payment_digest
        }
    )
    
    # Step 4: Launch token
    launch_resp = httpx.post(
        f"{BACKEND_URL}/api/v1/tokens/auto-create",
        json={
            "name": token_name,
            "symbol": ticker,
            "description": "",
            "initialSuiAmount": first_buy_sui,
            "migrateTo": 0,
            "creator": wallet_address,
            "paymentInvoiceId": invoice["invoiceId"],
            "paymentTxDigest": payment_digest
        }
    )
    
    return launch_resp.json()
```

---

## Error Codes

| Status | Error                        | Cause                              | Solution                        |
|--------|------------------------------|-------------------------------------|---------------------------------|
| 402    | "Payment required"            | Missing paymentInvoiceId            | Complete payment flow first      |
| 402    | "Payment not confirmed"       | Invoice not paid or unconfirmed     | Wait and check /status endpoint |
| 400    | "Invalid payment invoice"     | invoiceId not found or expired     | Get new invoice                 |
| 400    | "Invoice expired"             | Payment window elapsed             | Get new invoice                 |

---

## Disabling for Development

Set environment variable:
```bash
X402_ENABLED=false
```

Or in backend:
```python
PAYMENT_CONFIG = {
    "enabled": False,
    ...
}
```

---

## Security Considerations

1. **Invoice expiry**: Invoices expire after 5 minutes to prevent payment batching
2. **One-time use**: Each invoice can only be used once
3. **Amount validation**: Backend verifies exact amount sent
4. **Memo tracking**: Invoice ID in memo for payment correlation

---

## Fee Destination

Payments go to the Odyssey Treasury wallet:
```
0x13ced8aca378f70af8244d1c6a3d8a9564ad1032028ebbbee65f5c3a22d12733
```

This wallet is controlled by the protocol and used for:
- Protocol development funding
- Marketing initiatives
- Community incentives
