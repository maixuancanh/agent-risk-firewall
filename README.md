# Agent Risk Firewall

Pre-trade risk firewall for OKX Agentic Wallet workflows on X Layer and Solana.

Agent Risk Firewall is an OKX Plugin Store compatible Skill + Python CLI that helps an AI agent evaluate a proposed swap, token trade, or approval before it asks the user to sign. It does not trade, sign, broadcast, revoke approvals, or handle private keys. It only returns a deterministic JSON verdict: `allow`, `warn`, or `block`.

## Why This Exists

Agentic wallets let AI agents move from natural-language intent to on-chain execution. That creates a new safety requirement: the agent needs a consistent checkpoint before signing, especially for meme tokens, volatile routes, high slippage, suspicious approvals, or incomplete scan data.

This plugin acts as a guardrail between a trading agent and the signing step:

```text
User intent
  -> AI agent / trading skill
  -> OKX OnchainOS quote or unsigned transaction
  -> Agent Risk Firewall
  -> allow / warn / block
  -> signing flow only when safe or explicitly confirmed
```

## What It Checks

The MVP focuses on X Layer and Solana swaps and approvals.

| Area | Behavior |
| --- | --- |
| Input validation | Validates supported chains, operation type, wallet address format, token address format, quote shape, and transaction context. |
| OKX security data | Calls OKX OnchainOS token scan and transaction scan when available. |
| Simulation | Calls OKX OnchainOS gateway simulation when transaction context is available. |
| Liquidity | Reads token liquidity data when available. |
| Policy | Applies deterministic `balanced`, `strict`, `competition`, or `degen-small-size` profiles. |
| External evidence | Accepts optional GoPlus, Birdeye, and RootData evidence supplied by other plugins. |
| Approval risk | Checks unlimited approvals, EOA spenders, unknown spenders, allowlists, and denylists. |
| Audit trail | Returns `decisionId`, `policyVersion`, and `evidenceHash` for reviewability. |
| Output | Returns machine-readable JSON for agents. |

## Safety Boundaries

This plugin intentionally does not:

- Sign transactions
- Broadcast transactions
- Execute swaps
- Revoke approvals
- Store wallet history
- Store API credentials
- Request or handle private keys, seed phrases, or mnemonics
- Send wallet data to any backend outside OKX OnchainOS checks

If live scan or simulation data is unavailable, the plugin treats verification as incomplete and returns at least `warn`; it does not silently mark the operation as safe.

## Verdicts

| Verdict | Agent behavior |
| --- | --- |
| `allow` | The agent may continue the normal signing flow if the user already requested it. |
| `warn` | The agent must show the warning reasons and ask for explicit user confirmation before signing. |
| `block` | The agent must cancel the operation and must not ask the user to sign or broadcast. |

Example output:

```json
{
  "verdict": "warn",
  "riskScore": 62,
  "requiresUserConfirmation": true,
  "reasons": [
    {
      "code": "SLIPPAGE_ELEVATED",
      "severity": "warn",
      "message": "Quoted slippage is elevated."
    }
  ],
  "evidence": {},
  "audit": {
    "decisionId": "arf_0123456789abcdef",
    "policyProfile": "balanced",
    "policyVersion": "1.1.0",
    "evidenceHash": "64-character-sha256"
  },
  "safeNextStep": "Show the warning reasons and ask the user for explicit confirmation before signing."
}
```

## Policy Profiles

| Profile | Use case | Key behavior |
| --- | --- | --- |
| `balanced` | Default retail agentic trading guardrail | Blocks critical risk and warns on elevated risk. |
| `strict` | High-safety mode | Blocks unavailable scans, token `HIGH`, EOA spenders, and tighter slippage/price-impact limits. |
| `competition` | OKX Agentic Trading style workflows | Tighter caps and blocks stablecoin/native-only pairs. |
| `degen-small-size` | Small meme-token experiments | Higher slippage tolerance with a hard 25 USD trade cap. |

## Balanced Policy

| Signal | Result |
| --- | --- |
| Token `CRITICAL` on buy/swap | `block` |
| Token `CRITICAL` on sell | `warn` |
| Token `HIGH` or `MEDIUM` | `warn` |
| OKX tx-scan `block` | `block` |
| OKX tx-scan `warn` | `warn` |
| Simulation revert/failure | `block` |
| Scan or simulation timeout/unavailable | `warn` |
| Slippage `2%` to `5%` | `warn` |
| Slippage above `5%` | `block` |
| Price impact `3%` to `8%` | `warn` |
| Price impact above `8%` | `block` |
| Trade above `250 USD` | `block` |
| Trade above `10%` of wallet value, when wallet value is provided | `block` |

## Repository Layout

```text
skills/agent-risk-firewall/
  .claude-plugin/plugin.json
  plugin.yaml
  SKILL.md
  SUMMARY.md
  README.md
  LICENSE
  pyproject.toml
  src/agent_risk_firewall/
  tests/
```

## Local Installation

From the plugin directory:

```powershell
cd D:\pluginokx\skills\agent-risk-firewall
python -m pip install -e .
agent-risk-firewall self-test
```

Or run directly from source without installing:

```powershell
cd D:\pluginokx
$env:PYTHONPATH = "D:\pluginokx\skills\agent-risk-firewall\src"
python -m agent_risk_firewall self-test
```

## CLI Usage

Check a proposed trade or approval:

```powershell
agent-risk-firewall check --input request.json --format json
```

Read from stdin:

```powershell
Get-Content .\request.json | agent-risk-firewall check --input - --format json
```

Show the active policy:

```powershell
agent-risk-firewall policy --profile balanced
agent-risk-firewall policy --profile strict
agent-risk-firewall policy --profile competition
agent-risk-firewall policy --profile degen-small-size
```

Run local self-test:

```powershell
agent-risk-firewall self-test
```

## Input Contract

```json
{
  "chain": "xlayer",
  "operation": "swap",
  "walletAddress": "0x0000000000000000000000000000000000000000",
  "tokenIn": {
    "address": "0x0000000000000000000000000000000000000001",
    "symbol": "USDC",
    "decimals": 6
  },
  "tokenOut": {
    "address": "0x0000000000000000000000000000000000000002",
    "symbol": "TOKEN",
    "decimals": 18
  },
  "amountIn": "100",
  "amountInUsd": 100,
  "walletValueUsd": 1000,
  "quote": {
    "expectedOut": "12345",
    "slippagePct": 1,
    "priceImpactPct": 0.8,
    "route": ["OKX DEX"],
    "venue": "okx-dex"
  },
  "tx": {
    "from": "0x0000000000000000000000000000000000000000",
    "to": "0x0000000000000000000000000000000000000003",
    "data": "0x",
    "value": "0"
  },
  "approval": {
    "spender": "0x0000000000000000000000000000000000000004",
    "spenderType": "contract",
    "isUnlimited": false
  },
  "externalEvidence": {
    "goplus": {},
    "birdeye": {},
    "rootdata": {}
  },
  "policyProfile": "balanced"
}
```

Supported values:

- `chain`: `xlayer`, `solana`
- `operation`: `buy`, `sell`, `swap`, `approval`
- `policyProfile`: `balanced`, `strict`, `competition`, `degen-small-size`

## External Evidence

Agent Risk Firewall does not call GoPlus, Birdeye, or RootData directly. Strategy and analytics plugins can pass their findings through `externalEvidence`:

```json
{
  "externalEvidence": {
    "goplus": {
      "riskLevel": "HIGH",
      "is_honeypot": "0",
      "buy_tax": "10",
      "sell_tax": "10"
    },
    "birdeye": {
      "liquidityUsd": 12000,
      "top10HolderPercent": 72
    },
    "rootdata": {
      "riskLevel": "LOW",
      "tags": []
    }
  }
}
```

## Strategy Plugin Compatibility

Use this plugin as middleware between alpha generation and execution:

```text
xlayer-alpha-hunter -> unsigned swap -> agent-risk-firewall -> execute only if allowed
smart-tradex -> quote/tx context -> agent-risk-firewall -> warn/block gate
otto-alpha-sniper -> external evidence + tx context -> agent-risk-firewall -> final confirmation
```

The strategy plugin owns signal generation. Agent Risk Firewall owns the pre-sign risk decision.

## Testing

Run the full test suite:

```powershell
cd D:\pluginokx
$env:PYTHONDONTWRITEBYTECODE = "1"
python -m pytest .\skills\agent-risk-firewall\tests -q -p no:cacheprovider
```

Expected result:

```text
28 passed
```

Validate the plugin package for OKX Plugin Store:

```powershell
& "$env:USERPROFILE\.local\bin\plugin-store.exe" lint .\skills\agent-risk-firewall
```

Expected result:

```text
Plugin 'agent-risk-firewall' passed all checks
```

The test suite includes golden fixtures for:

- Token `HIGH`
- Token `CRITICAL`
- Transaction scan `warn`
- Transaction scan `block`
- Simulation revert
- Slippage thresholds
- Address and chain mismatch
- Scan timeout/unavailable
- Policy profiles
- External GoPlus/Birdeye/RootData evidence
- Approval-specific risk checks
- Audit trail determinism

## Live Dry-Run

For live OKX OnchainOS evidence, install and log in to OnchainOS first:

```powershell
npx skills add okx/onchainos-skills
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
onchainos wallet status
```

Use `onchainos swap swap` for unsigned transaction dry-runs. Do not use `onchainos swap execute` unless you intentionally want to sign and broadcast a real transaction.

## OKX Plugin Store Submission

This plugin is configured for OKX Plugin Store:

```yaml
name: agent-risk-firewall
category: security
build:
  lang: python
  source_repo: maixuancanh/agent-risk-firewall
  binary_name: agent-risk-firewall
```

Before opening a PR to `okx/plugin-store`, verify:

- `plugin-store lint` passes
- Tests pass
- No `.env`, credentials, `__pycache__`, `.pyc`, binaries, or build artifacts are included
- `plugin.yaml` uses a full 40-character `build.source_commit`
- The PR only modifies `skills/agent-risk-firewall/`

## Disclaimer

Agent Risk Firewall is a defensive pre-trade guardrail, not a guarantee of safety. On-chain data, third-party liquidity, scan results, and simulations can be incomplete, stale, or wrong. Trading and DeFi activity can cause loss of funds. Use dry-run mode first and start with small amounts.

## License

MIT
