# onlyfence-guardrails

Safety guardrails for AI agents executing crypto trades using OnlyFence.

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/seallabs/onlyfence/main/install.sh | sh
```

## Python Integration

```python
import subprocess
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class GuardrailConfig:
    max_single_trade: float  # Max $ per trade
    max_24h_volume: float      # Max $ per 24h
    allowed_tokens: list[str]  # Token type addresses
    
@dataclass
class GuardrailResult:
    allowed: bool
    reason: Optional[str] = None
    current_24h_volume: Optional[float] = None

class OnlyFenceGuardrails:
    def __init__(self, config_path: str = "~/.onlyfence/config.toml"):
        self.config_path = Path(config_path).expanduser()
        self.db_path = self.config_path.parent / "trades.db"
        self.binary = Path("~/.onlyfence/bin/fence").expanduser()
    
    def load_config(self) -> GuardrailConfig:
        """Load OnlyFence configuration."""
        config = {}
        if self.config_path.exists():
            with open(self.config_path) as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, val = line.split('=', 1)
                        config[key.strip()] = val.strip().strip('"')
        
        return GuardrailConfig(
            max_single_trade=float(config.get('max_single_trade', 200)),
            max_24h_volume=float(config.get('max_24h_volume', 500)),
            allowed_tokens=self._parse_tokens(config.get('tokens', ''))
        )
    
    def _parse_tokens(self, tokens_str: str) -> list[str]:
        """Parse tokens from config."""
        tokens = []
        in_list = False
        current = ""
        for char in tokens_str:
            if char == '[':
                in_list = True
            elif char == ']':
                if current.strip():
                    tokens.append(current.strip().strip(','))
                break
            elif char == ',' and in_list:
                if current.strip():
                    tokens.append(current.strip())
                current = ""
            else:
                current += char
        return tokens if tokens else ["SUI", "0x2::sui::SUI"]
    
    def get_24h_volume(self) -> float:
        """Get trading volume from last 24 hours."""
        if not self.db_path.exists():
            return 0.0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUM(amount_usd) 
                FROM trades 
                WHERE timestamp > datetime('now', '-24 hours')
            """)
            result = cursor.fetchone()[0]
            conn.close()
            return float(result) if result else 0.0
        except:
            return 0.0
    
    def check_trade(self, token_address: str, amount_usd: float) -> GuardrailResult:
        """
        Check if trade is allowed by guardrails.
        
        Args:
            token_address: The token type address
            amount_usd: Trade amount in USD
            
        Returns:
            GuardrailResult with allowed status and reason if blocked
        """
        config = self.load_config()
        
        # Check 1: Token in allowlist
        if token_address not in config.allowed_tokens:
            return GuardrailResult(
                allowed=False,
                reason=f"Token {token_address} not in allowlist"
            )
        
        # Check 2: Single trade limit
        if amount_usd > config.max_single_trade:
            return GuardrailResult(
                allowed=False,
                reason=f"Trade amount ${amount_usd} exceeds max ${config.max_single_trade}"
            )
        
        # Check 3: 24h volume limit
        volume_24h = self.get_24h_volume()
        if volume_24h + amount_usd > config.max_24h_volume:
            return GuardrailResult(
                allowed=False,
                reason=f"Would exceed 24h volume ${volume_24h + amount_usd} (max ${config.max_24h_volume})",
                current_24h_volume=volume_24h
            )
        
        return GuardrailResult(allowed=True)
    
    def log_trade(self, token_address: str, amount_usd: float, trade_type: str):
        """Log successful trade to OnlyFence database."""
        if not self.db_path.exists():
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO trades (token, amount_usd, type, timestamp)
                VALUES (?, ?, ?, datetime('now'))
            """, (token_address, amount_usd, trade_type))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to log trade: {e}")


# Usage Example
if __name__ == "__main__":
    guardrails = OnlyFenceGuardrails()
    
    # Check a trade
    result = guardrails.check_trade(
        token_address="0x...::AIDA",
        amount_usd=50.0
    )
    
    if result.allowed:
        print("Trade allowed!")
    else:
        print(f"Trade blocked: {result.reason}")
        if result.current_24h_volume:
            print(f"Current 24h volume: ${result.current_24h_volume}")
```

## Async Version (for Agent Loops)

```python
import asyncio
from typing import Optional

class AsyncOnlyFenceGuardrails:
    """Async version for use in agent loops."""
    
    def __init__(self):
        self.sync_guardrails = OnlyFenceGuardrails()
    
    async def check_trade_async(
        self, 
        token_address: str, 
        amount_usd: float
    ) -> GuardrailResult:
        """Async guardrail check."""
        # Run sync check in thread pool to not block
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.sync_guardrails.check_trade,
            token_address,
            amount_usd
        )
    
    async def execute_with_guardrails(
        self,
        token_address: str,
        amount_usd: float,
        trade_func,  # Async function to execute
        *args, **kwargs
    ):
        """
        Execute trade only if guardrails pass.
        
        Usage:
            result = await guardrails.execute_with_guardrails(
                token_address="0x...",
                amount_usd=100.0,
                trade_func=trader.buy_token,
                pool_id="0x...",
                sui_amount=10.0
            )
        """
        # Check guardrails
        check = await self.check_trade_async(token_address, amount_usd)
        
        if not check.allowed:
            return {
                "success": False,
                "blocked": True,
                "reason": check.reason
            }
        
        try:
            # Execute trade
            result = await trade_func(*args, **kwargs)
            
            # Log successful trade
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.sync_guardrails.log_trade,
                token_address,
                amount_usd,
                "buy" if "buy" in str(trade_func) else "sell"
            )
            
            return {
                "success": True,
                "blocked": False,
                "result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "blocked": False,
                "error": str(e)
            }
```

## Agent Loop Example

```python
async def agent_trade_loop(trader: OdysseyTrader, guardrails: AsyncOnlyFenceGuardrails):
    """Example agent loop with guardrails."""
    
    pending_trades = asyncio.Queue()
    
    while True:
        # Get next trade instruction
        instruction = await pending_trades.get()
        
        # Parse instruction
        action = instruction["action"]  # "buy" or "sell"
        token = instruction["token"]
        amount = instruction["amount"]
        
        # Convert to USD (would need price feed in real implementation)
        amount_usd = amount  # Assuming amount is already in USD
        
        # Guardrail check
        check = await guardrails.check_trade_async(token, amount_usd)
        
        if not check.allowed:
            print(f"Trade blocked: {check.reason}")
            continue
        
        # Execute trade
        if action == "buy":
            result = await trader.buy_token(
                pool_id=instruction["pool_id"],
                token_type=token,
                sui_amount=amount
            )
        else:
            result = await trader.sell_token(
                pool_id=instruction["pool_id"],
                token_type=token,
                token_amount=amount
            )
        
        print(f"Trade executed: {result}")
```

## Configuration

Edit `~/.onlyfence/config.toml`:

```toml
[chain.sui]
rpc = "https://fullnode.mainnet.sui.io:443"

[chain.sui.allowlist]
tokens = [
  "SUI",
  "0x2::sui::SUI",
  "0x...::AIDA",
]

[chain.sui.limits]
max_single_trade = 200      # $200 max per trade
max_24h_volume = 500        # $500 max per 24h
```

## CLI Commands

```bash
# Setup wallet
fence setup

# Check status
fence status

# View history
fence history

# Edit config
fence config edit
```

## Wallet

- Address: `0x1aeee25acbd3a5a62357e7266f749d5a62b26a89f540e52aa4fc534fba879959`
- Mnemonic (BACKUP): index loyal long response awake barrel that unable shoulder carry island dream distance test receive tuition betray fly chaos foil muffin core cruel pear
