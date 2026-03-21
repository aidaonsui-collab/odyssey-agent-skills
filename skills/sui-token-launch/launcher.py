"""
Odyssey Token Launcher

Autonomous AI agent skill for launching tokens on the Odyssey 2.0 bonding curve launchpad.
"""

import os
from dataclasses import dataclass
from typing import Optional, List
import json

# Contract addresses (mainnet)
ODYSSEY_PKG = "0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da"
MODULE = "moonbags"
CONFIG_OBJ = "0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f"
STAKE_CONFIG = "0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49"
LOCK_CONFIG = "0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006"
SUI_CLOCK = "0x0000000000000000000000000000000000000000000000000000000000000006"

# Bonding curve constants (calibrated to Moonbags)
VIRTUAL_TOKEN_RESERVES = 1_066_708_773_000_000_000  # ~1.067B tokens
VIRTUAL_SUI_START = 666_730_000  # ~0.667 SUI in mist
TOKEN_DECIMALS = 6
POOL_FEE_MIST = 10_000_000  # 0.01 SUI

# Pre-compiled coin module bytecode (base64 encoded)
COIN_BYTECODE_B64 = "oRzrCwYAAAAKAQAMAgweAyoiBEwIBVRUB6gBwAEI6AJgBsgDFArcAwUM4QMoAAcBDAIGAhACEQISAAACAAEBBwEAAAIBDAEAAQIDDAEAAQQEAgAFBQcAAAoAAQABCwEEAQACCAYHAQIDDQkBAQwDDg0BAQwEDwoLAAEDAgUDCAQMAggABwgEAAILAgEIAAsDAQgAAQgFAQsBAQkAAQgABwkAAgoCCgIKAgsBAQgFBwgEAgsDAQkACwIBCQABCwIBCAABCQABBggEAQUBCwMBCAACCQAFDUNPSU5fVEVNUExBVEUMQ29pbk1ldGFkYXRhBk9wdGlvbgtUcmVhc3VyeUNhcAlUeENvbnRleHQDVXJsBGNvaW4NY29pbl90ZW1wbGF0ZQ9jcmVhdGVfY3VycmVuY3kLZHVtbXlfZmllbGQEaW5pdARub25lBm9wdGlvbhRwdWJsaWNfZnJlZXplX29iamVjdA9wdWJsaWNfdHJhbnNmZXIGc2VuZGVSCHRyYW5zZmVyCnR4X2NvbnRleHQDdXJsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACCgIFBENPSU5fVEVNUExBVEUMQ29pbk1ldGFkYXRhCk9wdGlvbgtUcmVhc3VyeUNhcAlUeENvbnRleHQDVXJsBGNvaW4NY29pbl90ZW1wbGF0ZQ9jcmVhdGVfY3VycmVuY3kLZHVtbXlfZmllbGQEaW5pdARub25lBm9wdGlvbhRwdWJsaWNfZnJlZXplX29iamVjdA9wdWJsaWNfdHJhbnNmZXIGc2VuZGVSCHRyYW5zZmVyCnR4X2NvbnRleHQDdXJsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACCgIFBENPSU4KAgUEQ29pbgoCAQAAAgEJAQAAAAACEgsAMQkHAAcBBwI4AAoBOAEMAgwDCwI4AgsDCwEuEQU4AwIA"


@dataclass
class LaunchParams:
    """Parameters for token launch."""
    token_name: str
    ticker: str
    description: str
    first_buy_sui: float
    migrate_to: int  # 0=Cetus, 1=Turbos
    target_raise_sui: float
    twitter: str = ""
    telegram: str = ""
    website: str = ""
    image_url: str = ""


@dataclass
class LaunchResult:
    """Result of a token launch."""
    success: bool
    package_id: Optional[str] = None
    pool_id: Optional[str] = None
    digest: Optional[str] = None
    tokens_received: int = 0
    error: Optional[str] = None


class OdysseyLauncher:
    """
    AI agent skill for launching tokens on Odyssey 2.0.
    
    Usage:
        launcher = OdysseyLauncher()
        result = launcher.launch_token(
            token_name="My Token",
            ticker="MINE",
            description="A new token",
            first_buy_sui=50.0,
            migrate_to=0,
            target_raise_sui=2000.0
        )
    """
    
    def __init__(self, rpc_url: str = "https://fullnode.mainnet.sui.io:443"):
        """
        Initialize the launcher.
        
        Args:
            rpc_url: Sui RPC endpoint
        """
        self.rpc_url = rpc_url
        self._wallet = None
        
    def calculate_tokens(self, sui_amount: float) -> int:
        """
        Calculate tokens received for SUI input.
        
        Args:
            sui_amount: Amount of SUI to spend
            
        Returns:
            Number of tokens (raw, before decimal conversion)
        """
        sui_mist = int(sui_amount * 1e9)
        tokens_raw = (VIRTUAL_TOKEN_RESERVES * sui_mist) // (VIRTUAL_SUI_START + sui_mist)
        return tokens_raw
    
    def calculate_tokens_display(self, sui_amount: float) -> float:
        """
        Calculate tokens received (display amount with decimals).
        
        Args:
            sui_amount: Amount of SUI to spend
            
        Returns:
            Number of tokens (after decimal conversion)
        """
        return self.calculate_tokens(sui_amount) / (10 ** TOKEN_DECIMALS)
    
    def set_wallet(self, address: str, sign_fn=None):
        """
        Set wallet configuration.
        
        Args:
            address: Sui wallet address
            sign_fn: Optional signing function
        """
        self._wallet = {"address": address, "sign": sign_fn}
    
    def estimate_gas(self, num_actions: int = 5) -> int:
        """
        Estimate gas cost for a transaction.
        
        Args:
            num_actions: Number of actions in the transaction
            
        Returns:
            Gas estimate in mist
        """
        # Rough estimate: ~0.00005 SUI per action
        return int(50_000_000 * num_actions)
    
    def validate_params(self, params: LaunchParams) -> Optional[str]:
        """
        Validate launch parameters.
        
        Args:
            params: Launch parameters
            
        Returns:
            Error message if invalid, None if valid
        """
        if not params.token_name or len(params.token_name) > 50:
            return "Token name must be 1-50 characters"
        if not params.ticker or len(params.ticker) > 10:
            return "Ticker must be 1-10 characters"
        if not params.description or len(params.description) > 500:
            return "Description must be 1-500 characters"
        if params.first_buy_sui < 1:
            return "First buy must be at least 1 SUI"
        if params.target_raise_sui < 2000:
            return "Target raise must be at least 2000 SUI"
        if params.migrate_to not in [0, 1]:
            return "Migrate to must be 0 (Cetus) or 1 (Turbos)"
        return None
    
    def build_publish_tx(self) -> dict:
        """
        Build publish transaction for coin module.
        
        Returns:
            Transaction data (unsigned)
        """
        bytecode = bytes.fromhex(COIN_BYTECODE_B64)
        return {
            "kind": "publish",
            "modules": [bytecode],
            "gas_budget": 50_000_000
        }
    
    def build_create_pool_tx(
        self,
        package_id: str,
        treasury_cap_id: str,
        metadata_id: str,
        params: LaunchParams
    ) -> dict:
        """
        Build create pool transaction.
        
        Args:
            package_id: Published package ID
            treasury_cap_id: TreasuryCap object ID
            metadata_id: CoinMetadata object ID
            params: Launch parameters
            
        Returns:
            Transaction data (unsigned)
        """
        first_buy_mist = int(params.first_buy_sui * 1e9)
        target_raise_mist = int(params.target_raise_sui * 1e9)
        
        return {
            "kind": "move_call",
            "target": f"{ODYSSEY_PKG}::{MODULE}::create_and_lock_first_buy_with_fee",
            "type_arguments": [f"{package_id}::coin_template::COIN_TEMPLATE"],
            "arguments": {
                "config": CONFIG_OBJ,
                "stake_config": STAKE_CONFIG,
                "lock_config": LOCK_CONFIG,
                "treasury_cap": treasury_cap_id,
                "fee": str(POOL_FEE_MIST),
                "migrate_to": params.migrate_to,
                "first_buy": str(first_buy_mist),
                "target_raise": str(target_raise_mist),
                "token_name": params.token_name,
                "ticker": params.ticker.upper(),
                "image": params.image_url,
                "description": params.description,
                "twitter": params.twitter,
                "telegram": params.telegram,
                "website": params.website,
            },
            "gas_budget": 50_000_000
        }
    
    def launch_token(self, params: LaunchParams, dry_run: bool = False) -> LaunchResult:
        """
        Launch a new token on Odyssey.
        
        Args:
            params: Launch parameters
            dry_run: If True, simulate without executing
            
        Returns:
            LaunchResult with success status and details
        """
        # Validate
        error = self.validate_params(params)
        if error:
            return LaunchResult(success=False, error=error)
        
        # Calculate expected tokens
        tokens_raw = self.calculate_tokens(params.first_buy_sui)
        tokens_display = tokens_raw / (10 ** TOKEN_DECIMALS)
        
        # Build transactions
        publish_tx = self.build_publish_tx()
        
        if dry_run:
            return LaunchResult(
                success=True,
                tokens_received=tokens_display,
                error="(dry run - no transactions executed)"
            )
        
        # TODO: Execute transactions via Sui RPC
        # For now, return the built transactions for external execution
        return LaunchResult(
            success=True,
            tokens_received=tokens_display,
            error="Execution not implemented - use with Sui SDK"
        )


# Tool schema for agent frameworks
TOOL_SCHEMA = {
    "name": "odyssey_launch_token",
    "description": "Launch a new token on Odyssey 2.0 bonding curve launchpad",
    "parameters": {
        "type": "object",
        "properties": {
            "token_name": {
                "type": "string",
                "description": "Name of the token (1-50 chars)"
            },
            "ticker": {
                "type": "string", 
                "description": "Ticker symbol (1-10 chars)"
            },
            "description": {
                "type": "string",
                "description": "Token description (1-500 chars)"
            },
            "first_buy_sui": {
                "type": "number",
                "description": "Initial SUI to contribute to pool"
            },
            "migrate_to": {
                "type": "integer",
                "enum": [0, 1],
                "description": "0=Cetus, 1=Turbos"
            },
            "target_raise_sui": {
                "type": "number",
                "description": "Target raise amount (min 2000 SUI)"
            },
            "twitter": {
                "type": "string",
                "description": "Twitter URL (optional)"
            },
            "telegram": {
                "type": "string",
                "description": "Telegram URL (optional)"
            },
            "website": {
                "type": "string", 
                "description": "Website URL (optional)"
            },
            "image_url": {
                "type": "string",
                "description": "Token logo URL (optional)"
            },
            "dry_run": {
                "type": "boolean",
                "description": "Simulate without executing"
            }
        },
        "required": ["token_name", "ticker", "description", "first_buy_sui", "migrate_to", "target_raise_sui"]
    }
}


if __name__ == "__main__":
    # Example usage
    launcher = OdysseyLauncher()
    
    params = LaunchParams(
        token_name="Test Token",
        ticker="TEST",
        description="A test token on Odyssey",
        first_buy_sui=50.0,
        migrate_to=0,  # Cetus
        target_raise_sui=2000.0
    )
    
    # Dry run to estimate
    result = launcher.launch_token(params, dry_run=True)
    print(f"Success: {result.success}")
    print(f"Tokens received: {result.tokens_received}")
    print(f"Error: {result.error}")
