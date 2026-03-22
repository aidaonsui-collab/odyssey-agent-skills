# Sui RPC Reference

## Common RPC Endpoints

### SuiClient (pysui)

```python
from pysui import SuiClient, SuiConfig

# Default mainnet
client = SuiClient(SuiConfig.default())

# Custom RPC
client = SuiClient(SuiConfig(network="mainnet", rpc_url="https://sui-mainnet-rpc.allthatnode.com"))
```

### Get Balance

```python
# Get SUI balance
balance = client.get_balance(address)
print(f"SUI balance: {balance.total_balance}")

# Get specific coin balance
balance = client.get_balance(address, "0x2::sui::SUI")
```

### Get Coins

```python
# Get all SUI coins
coins = client.get_coins(address, "0x2::sui::SUI")
for coin in coins:
    print(f"Coin: {coin.coin_object_id}, Amount: {coin.balance}")
```

### Get Transaction

```python
tx = client.get_transaction_block("4xDhZGCMhH6B1eZoPGhKJijJ3n1iKG5vFpL5r3L9mWZtF")
print(f"Status: {tx.effects.status.status}")
print(f"Gas used: {tx.effects.gas_used}")
```

### Get Object

```python
obj = client.get_object("0xYOUR_OBJECT_ID")
print(f"Type: {obj.data.type}")
print(f"Fields: {obj.data.content}")
```

---

## Transaction Building

### Basic Transfer

```python
from pysui.sui_txn import Transaction

tx = Transaction()
tx.move_call(
    target="0x2::transfer::public_transfer",
    type_arguments=["0x2::sui::SUI"],
    arguments=[
        tx.object("0xCOIN_OBJECT_ID"),
        tx.pure.address("0xRECIPIENT_ADDRESS")
    ]
)

result = client.sign_and_execute(tx, wallet="0xWALLET_ADDRESS")
print(f"Digest: {result.digest}")
```

### Split and Transfer

```python
tx = Transaction()

# Split coin into two
split_result = tx.split_coin(
    coin=tx.object("0xCOIN_OBJECT_ID"),
    amounts=[1000000000, 500000000],  # 1 SUI, 0.5 SUI
)
tx.transfer(split_result[0], tx.pure.address("0xRECIPIENT1"))
tx.transfer(split_result[1], tx.pure.address("0xRECIPIENT2"))

client.sign_and_execute(tx, wallet="0xWALLET_ADDRESS")
```

### Publish Module

```python
tx = Transaction()

# Read compiled module bytecode
with open("./my_module.module", "rb") as f:
    bytecode = list(f.read())

# Publish
upgrade_cap = tx.publish([bytecode])
tx.set_gas_budget(50_000_000)

result = client.sign_and_execute(tx, wallet="0xWALLET_ADDRESS")

# Extract new package ID
for obj in result.created:
    if "package" in str(obj.type_).lower():
        package_id = obj.object_id
```

---

## Event Parsing

### Get Events by Type

```python
events = client.get_events({
    "MoveEventType": "0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da::moonbags::PoolCreated"
})

for event in events:
    print(f"Type: {event.type}")
    print(f"Parsed: {event.parsed_json}")
```

### Parse Pool Events

```python
# After creating a pool, listen for PoolCreated event
pool_created_events = client.get_events({
    "MoveEvent": {
        "package": "0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da",
        "module": "moonbags"
    }
})

for event in pool_created_events:
    if event.type == "PoolCreated":
        pool_id = event.parsed_json.get("pool_id")
        token_type = event.parsed_json.get("token_type")
        print(f"New pool: {pool_id}")
```

---

## Common Types

### Object Reference

```python
from pysui.sui_types import ObjectRef

ref = ObjectRef(
    object_id="0x...",
    version=1,
    digest="..."
)
```

### Gas Budget

```python
# Set gas budget in mist (1 SUI = 1e9 mist)
tx.set_gas_budget(50_000_000)  # 0.05 SUI
tx.set_gas_budget(100_000_000)  # 0.1 SUI
```

---

## Mainnet RPC URLs

```python
MAINNET_RPCS = [
    "https://sui-mainnet-rpc.allthatnode.com",
    "https://fullnode.mainnet.sui.io:443",
    "https://rpc-mainnet.sui.io",
]

TESTNET_RPCS = [
    "https://sui-testnet-rpc.allthatnode.com",
    "https://fullnode.testnet.sui.io:443",
]
```

---

## Error Handling

```python
from pysui.exception import SuiRpcError

try:
    result = client.get_transaction_block("invalid_digest")
except SuiRpcError as e:
    print(f"RPC Error: {e.code}")
    print(f"Message: {e.message}")
```

---

## Keypair Management

```python
from pysui import SuiClient, SuiConfig
from pysui.keypair import Keypair
from pysui.mnemonic import derive_keypair_from_mnemonic

# From mnemonic
keypair = derive_keypair_from_mnemonic("word1 word2 ... word24")
address = keypair.public_key().to_sui_address()

# Load from environment
config = SuiConfig.from_env()
client = SuiClient(config)
```

---

## Monitoring

### Wait for Transaction

```python
# Poll until confirmed
def wait_for_tx(client, digest, timeout_ms=60000):
    import time
    start = time.time()
    while time.time() - start < timeout_ms / 1000:
        try:
            tx = client.get_transaction_block(digest)
            if tx.effects.status.status == "success":
                return tx
        except:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"Transaction {digest} not confirmed")
```

---

## Useful Queries

### Get All Coins for Address

```python
def get_all_coins(client, address):
    """Get all coins for an address, handling pagination."""
    coins = []
    cursor = None
    while True:
        result = client.get_coins(address, None, cursor=cursor, limit=100)
        coins.extend(result.data)
        if result.has_next_page:
            cursor = result.next_cursor
        else:
            break
    return coins
```

### Get Owned Objects

```python
objects = client.get_owned_objects(address)
for obj in objects:
    print(f"{obj.data.object_id}: {obj.data.type}")
```
