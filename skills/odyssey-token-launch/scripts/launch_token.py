#!/usr/bin/env python3
"""
Odyssey Token Launch Script

Complete token launch workflow with x402 payment.
"""

import asyncio
import argparse
import os
import sys
from dataclasses import dataclass
from typing import Optional

import httpx

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============== CONFIG ==============

BACKEND_URL = os.getenv("ODYSSEY_BACKEND_URL", "https://your-odyssey-backend.railway.app")
PAYMENT_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes


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
class Invoice:
    invoice_id: str
    amount_sui: float
    pay_to: str
    expires_at: int


# ============== BONDING CURVE MATH ==============

VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000
VIRTUAL_SUI_START = 666_730_000
TOKEN_DECIMALS = 6


def calculate_tokens(sui_amount: float) -> float:
    """Calculate tokens received for SUI input."""
    sui_mist = int(sui_amount * 1e9)
    tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
    return tokens_raw / (10 ** TOKEN_DECIMALS)


# ============== PAYMENT FLOW ==============

async def get_invoice() -> Invoice:
    """Get a payment invoice from backend."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/api/v1/payment/invoice", timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        return Invoice(
            invoice_id=data["invoiceId"],
            amount_sui=data["amountSui"],
            pay_to=data["payTo"],
            expires_at=data["expiresAt"]
        )


async def check_payment_status(invoice_id: str) -> dict:
    """Check payment status for an invoice."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BACKEND_URL}/api/v1/payment/status/{invoice_id}",
            timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()


async def confirm_payment(invoice_id: str, tx_digest: str) -> dict:
    """Confirm payment with transaction digest."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/payment/confirm",
            json={"invoiceId": invoice_id, "txDigest": tx_digest},
            timeout=10.0
        )
        resp.raise_for_status()
        return resp.json()


# ============== LAUNCH FLOW ==============

async def launch_token(params: LaunchParams, invoice: Invoice, tx_digest: str) -> dict:
    """Launch token with payment proof."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/api/v1/tokens/auto-create",
            json={
                "name": params.name,
                "symbol": params.ticker,
                "description": params.description,
                "initialSuiAmount": params.first_buy_sui,
                "migrateTo": params.migrate_to,
                "creator": "",  # Will be filled by backend
                "paymentInvoiceId": invoice.invoice_id,
                "paymentTxDigest": tx_digest,
            },
            timeout=30.0
        )
        resp.raise_for_status()
        return resp.json()


# ============== MAIN ==============

async def main():
    parser = argparse.ArgumentParser(description="Launch token on Odyssey 2.0")
    parser.add_argument("--name", required=True, help="Token name")
    parser.add_argument("--ticker", "-t", required=True, help="Ticker symbol")
    parser.add_argument("--sui", "-s", type=float, default=50.0, help="First buy SUI")
    parser.add_argument("--description", "-d", default="", help="Token description")
    parser.add_argument("--migrate", "-m", choices=["cetus", "turbos"], default="cetus",
                       help="Migration target")
    parser.add_argument("--target", type=float, default=2000.0, help="Target raise")
    parser.add_argument("--dry-run", action="store_true", help="Simulate only")
    
    args = parser.parse_args()
    
    params = LaunchParams(
        name=args.name,
        ticker=args.ticker.upper(),
        description=args.description,
        first_buy_sui=args.sui,
        migrate_to=0 if args.migrate == "cetus" else 1,
        target_raise_sui=args.target
    )
    
    print(f"🚀 Launching {params.name} (${params.ticker})")
    print(f"   First buy: {params.first_buy_sui} SUI")
    print(f"   Target: {params.target_raise_sui} SUI")
    print(f"   Migrate to: {args.migrate.upper()}")
    print()
    
    # Calculate expected tokens
    expected_tokens = calculate_tokens(params.first_buy_sui)
    print(f"   Expected tokens: {expected_tokens:,.2f}")
    print()
    
    if args.dry_run:
        print("✅ Dry run - no transactions executed")
        return
    
    # Step 1: Get invoice
    print("📋 Step 1: Getting payment invoice...")
    try:
        invoice = await get_invoice()
        print(f"   Invoice: {invoice.invoice_id}")
        print(f"   Amount: {invoice.amount_sui} SUI")
        print(f"   Pay to: {invoice.pay_to[:20]}...")
    except Exception as e:
        print(f"   ❌ Failed to get invoice: {e}")
        print("   Make sure X402_ENABLED=true on backend")
        return
    
    print()
    print("⚠️  PAYMENT REQUIRED")
    print(f"   Send exactly {invoice.amount_sui} SUI to:")
    print(f"   {invoice.pay_to}")
    print(f"   With memo: {invoice.invoice_id}")
    print()
    print("   Then call with --confirm <tx_digest>")
    print()


if __name__ == "__main__":
    asyncio.run(main())
