#!/usr/bin/env python3
"""
Complete Token Launch Template

Full implementation showing how to:
1. Get x402 payment invoice
2. Send SUI payment (requires wallet integration)
3. Confirm payment
4. Launch token
5. Build and execute create_pool transaction

This is a reference implementation - actual usage requires pysui integration.
"""

import asyncio
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any


# ============== CONFIGURATION ==============

BACKEND_URL = "https://your-odyssey-backend.railway.app"

# Odyssey Contract Addresses (Mainnet)
ODYSSEY_PKG = "0x8127c4334e6a2e8ed51a631334762866efddd7c42cb20f131df3fed8db7bd870"
MODULE = "moonbags"
CONFIG_OBJ = "0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f"
STAKE_CONFIG = "0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49"
LOCK_CONFIG = "0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006"
SUI_CLOCK = "0x0000000000000000000000000000000000000000000000000000000000000006"

# Bonding Curve Constants
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000
VIRTUAL_SUI_START = 666_730_000
TOKEN_DECIMALS = 6
POOL_FEE_MIST = 10_000_000  # 0.01 SUI


# ============== DATA CLASSES ==============

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


@dataclass
class LaunchResult:
    success: bool
    token_name: str
    ticker: str
    package_id: Optional[str] = None
    pool_id: Optional[str] = None
    token_type: Optional[str] = None
    tx_digest: Optional[str] = None
    tokens_received: float = 0.0
    error: Optional[str] = None


# ============== BONDING CURVE ==============

def calculate_buy_tokens(sui_amount: float) -> tuple[int, float]:
    """Calculate tokens for SUI input. Returns (raw, display)."""
    sui_mist = int(sui_amount * 1e9)
    tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
    tokens_display = tokens_raw / (10 ** TOKEN_DECIMALS)
    return tokens_raw, tokens_display


def calculate_sell_tokens(sui_amount: float) -> tuple[int, float]:
    """Calculate SUI for tokens. Returns (mist, display)."""
    tokens_raw = int(sui_amount * (10 ** TOKEN_DECIMALS))
    sui_mist = (VIRTUAL_SUI_START * tokens_raw) // (VIRTUAL_TOKEN_RESERVES + tokens_raw)
    return sui_mist, sui_mist / 1e9


# ============== HTTP CLIENT ==============

import httpx


async def get_invoice() -> Dict[str, Any]:
    """Get payment invoice from backend."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/api/v1/payment/invoice")
        resp.raise_for_status()
        return resp.json()


async def confirm_payment(invoice_id: str, tx_digest: str) -> Dict[str, Any]:
    """Confirm payment with backend."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/payment/confirm",
            json={"invoiceId": invoice_id, "txDigest": tx_digest}
        )
        resp.raise_for_status()
        return resp.json()


async def auto_create_token(params: LaunchParams, invoice_id: str, tx_digest: str) -> Dict[str, Any]:
    """Call auto-create endpoint."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/tokens/auto-create",
            json={
                "name": params.name,
                "symbol": params.ticker,
                "description": params.description,
                "initialSuiAmount": params.first_buy_sui,
                "migrateTo": params.migrate_to,
                "targetRaise": params.target_raise_sui,
                "creator": "",  # Filled by backend from payment tx
                "paymentInvoiceId": invoice_id,
                "paymentTxDigest": tx_digest,
            }
        )
        resp.raise_for_status()
        return resp.json()


# ============== WALLET INTEGRATION ==============

def build_payment_tx(wallet_address: str, pay_to: str, amount_sui: float, memo: str) -> dict:
    """
    Build SUI payment transaction.
    
    In production, use pysui:
    ```python
    from pysui.sui_txn import Transaction
    
    tx = Transaction()
    coins = client.get_coins(wallet_address, "0x2::sui::SUI")
    
    # Split exact amount
    split = tx.split_coin(coins[0], [int(amount_sui * 1e9)])
    
    # Transfer with memo (as note/description)
    tx.transfer(split, tx.pure.address(pay_to))
    
    result = client.sign_and_execute(tx, wallet=wallet_address)
    return result.digest
    ```
    """
    return {
        "kind": "move_call",
        "target": "0x2::transfer::public_transfer",
        "type_arguments": ["0x2::sui::SUI"],
        "arguments": {
            "coin": "<COIN_OBJECT_ID>",
            "recipient": pay_to,
        },
        "gas_budget": 10_000_000
    }


def build_create_pool_tx(
    params: LaunchParams,
    package_id: str,
    treasury_cap_id: str,
    token_type: str
) -> dict:
    """
    Build create_pool transaction.
    
    In production, use pysui:
    ```python
    from pysui.sui_txn import Transaction
    
    tx = Transaction()
    tx.move_call(
        target=f"{ODYSSEY_PKG}::{MODULE}::create_and_lock_first_buy_with_fee",
        type_arguments=[token_type],
        arguments=[
            tx.object(CONFIG_OBJ),           # config
            tx.object(STAKE_CONFIG),         # stake_config
            tx.object(LOCK_CONFIG),           # lock_config
            tx.object(treasury_cap_id),       # treasury_cap
            tx.pure.u64(POOL_FEE_MIST),      # fee
            tx.pure.u8(params.migrate_to),   # migrate_to
            tx.pure.u64(int(params.first_buy_sui * 1e9)),  # first_buy
            tx.pure.u64(int(params.target_raise_sui * 1e9)),  # target_raise
            tx.pure.string(params.name),
            tx.pure.string(params.ticker.upper()),
            tx.pure.string(params.image_url),
            tx.pure.string(params.twitter),
            tx.pure.string(params.telegram),
            tx.pure.string(params.website),
            tx.pure.option(),  # fee_recipient_handle
        ]
    )
    tx.set_gas_budget(50_000_000)
    ```
    """
    return {
        "kind": "move_call",
        "target": f"{ODYSSEY_PKG}::{MODULE}::create_and_lock_first_buy_with_fee",
        "type_arguments": [token_type],
        "arguments": {
            "config": CONFIG_OBJ,
            "stake_config": STAKE_CONFIG,
            "lock_config": LOCK_CONFIG,
            "treasury_cap": treasury_cap_id,
            "fee": str(POOL_FEE_MIST),
            "migrate_to": params.migrate_to,
            "first_buy": str(int(params.first_buy_sui * 1e9)),
            "target_raise": str(int(params.target_raise_sui * 1e9)),
            "name": params.name,
            "symbol": params.ticker.upper(),
            "image_url": params.image_url,
            "x_social": params.twitter,
            "telegram_social": params.telegram,
            "website": params.website,
            "fee_recipient_handle": None,
        },
        "gas_budget": 50_000_000
    }


# ============== COMPLETE WORKFLOW ==============

async def complete_launch_flow(
    params: LaunchParams,
    wallet_address: str,
    execute_fn=None  # Function to sign and execute transactions
) -> LaunchResult:
    """
    Complete token launch workflow.
    
    Args:
        params: Launch parameters
        wallet_address: Agent's Sui wallet address
        execute_fn: Async function(wallet, tx_dict) -> tx_digest
    
    Returns:
        LaunchResult with success status and details
    """
    try:
        # Step 1: Get invoice
        print("📋 Getting payment invoice...")
        invoice = await get_invoice()
        print(f"   Invoice: {invoice['invoiceId']}")
        print(f"   Amount: {invoice['amountSui']} SUI")
        
        # Step 2: Send payment
        print("💸 Sending payment...")
        payment_tx = build_payment_tx(
            wallet_address,
            invoice['payTo'],
            invoice['amountSui'],
            invoice['invoiceId']
        )
        payment_digest = await execute_fn(wallet_address, payment_tx)
        print(f"   Payment TX: {payment_digest}")
        
        # Step 3: Confirm payment
        print("✅ Confirming payment...")
        confirm_result = await confirm_payment(invoice['invoiceId'], payment_digest)
        if confirm_result.get('status') != 'confirmed':
            return LaunchResult(
                success=False,
                token_name=params.name,
                ticker=params.ticker,
                error=f"Payment not confirmed: {confirm_result}"
            )
        
        # Step 4: Auto-create token
        print("🚀 Creating token...")
        create_result = await auto_create_token(
            params,
            invoice['invoiceId'],
            payment_digest
        )
        
        if not create_result.get('success'):
            return LaunchResult(
                success=False,
                token_name=params.name,
                ticker=params.ticker,
                error=create_result.get('error', 'Unknown error')
            )
        
        package_id = create_result['packageId']
        treasury_cap_id = create_result['treasuryCapId']
        token_type = create_result['tokenType']
        
        print(f"   Package: {package_id}")
        print(f"   TreasuryCap: {treasury_cap_id}")
        
        # Step 5: Build and execute create_pool
        print("🏊 Creating pool...")
        create_pool_tx = build_create_pool_tx(
            params,
            package_id,
            treasury_cap_id,
            token_type
        )
        pool_digest = await execute_fn(wallet_address, create_pool_tx)
        print(f"   Pool TX: {pool_digest}")
        
        # Calculate expected tokens
        _, tokens_display = calculate_buy_tokens(params.first_buy_sui)
        
        return LaunchResult(
            success=True,
            token_name=params.name,
            ticker=params.ticker,
            package_id=package_id,
            token_type=token_type,
            tx_digest=pool_digest,
            tokens_received=tokens_display
        )
        
    except Exception as e:
        return LaunchResult(
            success=False,
            token_name=params.name,
            ticker=params.ticker,
            error=str(e)
        )


# ============== EXAMPLE USAGE ==============

async def main():
    params = LaunchParams(
        name="Example Token",
        ticker="EXAMPLE",
        description="An example token launched via AI agent",
        first_buy_sui=50.0,
        migrate_to=0,
        target_raise_sui=5000.0
    )
    
    # Example wallet (replace with actual)
    wallet_address = "0x1234567890abcdef"
    
    # Mock execute function (replace with actual pysui)
    async def mock_execute(wallet, tx):
        print(f"   [MOCK] Would execute: {tx['kind']}")
        return "4xDhZGCMhH6B1eZoPGhKJijJ3n1iKG5vFpL5r3L9mWZtF"
    
    # Run in dry-run mode
    print("🧪 DRY RUN MODE\n")
    result = await complete_launch_flow(params, wallet_address, mock_execute)
    
    print("\n" + "=" * 50)
    print("RESULT:")
    print("=" * 50)
    print(f"Success: {result.success}")
    print(f"Token: {result.token_name} (${result.ticker})")
    if result.success:
        print(f"Package: {result.package_id}")
        print(f"Token Type: {result.token_type}")
        print(f"Tokens: {result.tokens_received:,.2f}")
        print(f"TX: {result.tx_digest}")
    else:
        print(f"Error: {result.error}")


if __name__ == "__main__":
    asyncio.run(main())
