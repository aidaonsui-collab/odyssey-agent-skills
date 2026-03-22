# Contract API Reference

## Mainnet Contract Addresses

| Contract          | Address                                                |
|-------------------|--------------------------------------------------------|
| Odyssey Package   | `0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da` |
| Module            | `moonbags`                                             |
| Configuration     | `0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f` |
| Stake Config      | `0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49` |
| Lock Config       | `0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006` |
| SUI Clock         | `0x0000000000000000000000000000000000000000000000000000000000000006` |
| SUI Coin          | `0x2::sui::SUI`                                        |

---

## Object Addresses

### Configuration Objects

```
0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f
└─ OdysseyConfig
    ├── fee_percent: u64
    ├── min_stake: u64
    └── max_stake: u64

0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006
└─ LockConfig
    ├── unlock_time: u64
    └── cliff_time: u64

0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49
└─ StakeConfig
    ├── rewards_pool: ID
    └── emission_rate: u64
```

---

## Module: `moonbags`

### Key Functions

#### `create_and_lock_first_buy_with_fee`

```move
public entry fun create_and_lock_first_buy_with_fee(
    config: &mut OdysseyConfig,
    stake_config: &StakeConfig,
    lock_config: &LockConfig,
    treasury_cap: &mut TreasuryCap<COIN>,
    fee: u64,
    migrate_to: u8,
    first_buy: u64,
    target_raise: u64,
    name: string::String,
    symbol: string::String,
    image_url: string::String,
    x_social: string::String,
    telegram_social: string::String,
    website: string::String,
    fee_recipient_handle: Option<string::String>,
    ctx: &mut TxContext
)
```

**Arguments:**
| Parameter             | Type         | Description                          |
|-----------------------|--------------|--------------------------------------|
| `config`              | `OdysseyConfig&mut` | Platform configuration           |
| `stake_config`        | `StakeConfig&`     | Staking configuration           |
| `lock_config`         | `LockConfig&`      | Lock configuration             |
| `treasury_cap`        | `TreasuryCap<COIN>&mut` | Token supply control      |
| `fee`                 | `u64`               | Pool creation fee in SUI mist |
| `migrate_to`          | `u8`                | 0=Cetus, 1=Turbos          |
| `first_buy`           | `u64`               | Initial SUI amount (mist)     |
| `target_raise`        | `u64`               | Target raise amount (mist)    |
| `name`                | `String`            | Token name                     |
| `symbol`              | `String`            | Ticker symbol                 |
| `image_url`           | `String`            | Logo URL                       |
| `x_social`            | `String`            | Twitter URL                    |
| `telegram_social`      | `String`            | Telegram URL                  |
| `website`              | `String`            | Website URL                   |

#### `buy`

```move
public entry fun buy<COIN>(
    pool: &mut Pool,
    payment: coin::Coin<SUI>,
    min_tokens_out: u64,
    clock: &Clock,
    ctx: &mut TxContext
)
```

**Arguments:**
| Parameter       | Type           | Description                    |
|-----------------|----------------|--------------------------------|
| `pool`          | `Pool&mut`     | Token pool                     |
| `payment`       | `Coin<SUI>`    | SUI coin to spend              |
| `min_tokens_out`| `u64`          | Minimum tokens to receive      |
| `clock`         | `Clock&`       | Sui clock for time-based ops   |

#### `sell`

```move
public entry fun sell<COIN>(
    pool: &mut Pool,
    tokens: coin::Coin<COIN>,
    min_sui_out: u64,
    clock: &Clock,
    ctx: &mut TxContext
)
```

---

## Type Strings

Full type string format for Move calls:
```
<package_id>::<module_name>::<struct_name>
```

Example:
```
0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da::moonbags::COIN_TEMPLATE
```

---

## Transaction Builder (TypeScript)

```typescript
import { TransactionBlock } from '@mysten/sui/transactions';

const tx = new Transaction();

// Example: Create pool
tx.moveCall({
  target: '0x50e60400cc2ea760b5fb8380fa3f1fc0a94dfc592ec78487313d21b50af846da::moonbags::create_and_lock_first_buy_with_fee',
  typeArguments: ['0xYOUR_PACKAGE::your_module::YOUR_TOKEN'],
  arguments: [
    tx.object('0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f'), // config
    tx.object('0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49'), // stake_config
    tx.object('0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006'), // lock_config
    tx.object('0xYOUR_TREASURY_CAP'), // treasury_cap
    tx.pure.u64(10_000_000), // fee (0.01 SUI)
    tx.pure.u8(0), // migrate_to (0=Cetus)
    tx.pure.u64(50_000_000_000), // first_buy (50 SUI in mist)
    tx.pure.u64(2_000_000_000_000), // target_raise (2000 SUI in mist)
    tx.pure.string('My Token'),
    tx.pure.string('MINE'),
    tx.pure.string(''),
    tx.pure.string(''),
    tx.pure.string(''),
    tx.pure.string(''),
    tx.pure.option(), // fee_recipient_handle
  ],
});

tx.setGasBudget(50_000_000);
```

---

## Object IDs in Transactions

When building transactions, these objects are always referenced:

| Object        | ID                                                           | Mutable |
|---------------|--------------------------------------------------------------|---------|
| Config        | `0x1fd45c94f890d3748e002c3636ea0dfc6e3bca0823269cb4119800369b43b07f` | Yes     |
| Stake Config  | `0x9e5b64163883d58ff8a52bc566b59f383ea88d69907986c19dc57018171e6f49` | No      |
| Lock Config   | `0xef887ab6838b42171ba5f1a645f10724d4960a1cefab216a0269e5ac5a531006` | No      |
| SUI Clock     | `0x0000000000000000000000000000000000000000000000000000000000000006` | No      |
