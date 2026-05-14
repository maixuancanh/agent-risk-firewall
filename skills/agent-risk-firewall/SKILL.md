---
name: agent-risk-firewall
description: "Pre-trade risk firewall for Agentic Wallet swaps on X Layer and Solana"
version: "1.0.0"
author: "Agent Risk Firewall Contributors"
tags:
  - security
  - risk
  - agentic-wallet
  - xlayer
  - solana
  - trading
---

# Agent Risk Firewall

## Overview

Agent Risk Firewall is a pre-trade guardian for Agentic Wallet workflows. Use it before any X Layer or Solana swap, token buy, token sell, or approval when an agent has quote or transaction context and is about to ask the user to sign.

The firewall does not sign transactions, broadcast transactions, revoke approvals, or execute swaps. It normalizes the proposed operation, calls OKX OnchainOS security and simulation commands when available, applies a deterministic balanced policy, and returns `allow`, `warn`, or `block`.

## Pre-flight Checks

Before using this skill, ensure:

1. Python 3.8+ is available.
2. The `agent-risk-firewall` command is installed from this plugin.
3. For live OKX checks, install OnchainOS skills with `npx skills add okx/onchainos-skills`.
4. For production usage, configure personal OKX credentials through the OnchainOS environment variables. Never commit `.env` files or API keys.

If `onchainos` is not installed or a scan fails, treat that as incomplete verification. The firewall will return at least `warn`; do not treat unavailable scan data as safe.

## Commands

### Check a proposed trade or approval

```bash
agent-risk-firewall check --input request.json --format json
```

**When to use**: Run this before any X Layer or Solana swap, token buy, token sell, or approval when the agent has quote or transaction context and is about to request a signature.

**Output**: JSON containing `verdict`, `riskScore`, `requiresUserConfirmation`, `reasons`, normalized `evidence`, and `safeNextStep`.

**Example**:

```bash
agent-risk-firewall check --input request.json --format json
```

Use `--input -` to read JSON from stdin.

Required input shape:

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
  "policyProfile": "balanced"
}
```

Output:

```json
{
  "verdict": "warn",
  "riskScore": 60,
  "requiresUserConfirmation": true,
  "reasons": [
    {
      "code": "TOKEN_HIGH",
      "severity": "warn",
      "message": "Target token has HIGH risk."
    }
  ],
  "evidence": {},
  "safeNextStep": "Show the warning reasons and ask the user for explicit confirmation before signing."
}
```

Agent behavior:

- `allow`: continue the signing or broadcast flow if the user already requested it.
- `warn`: show the warning reasons and require explicit user confirmation before continuing.
- `block`: do not request a signature, do not broadcast, and recommend canceling or revising the operation.

### Show the active policy

```bash
agent-risk-firewall policy --profile balanced
```

**When to use**: Run this when the user asks what thresholds the firewall applies, or before integrating the firewall into another trading skill.

**Output**: JSON describing supported chains, max trade size, wallet exposure cap, slippage thresholds, price impact thresholds, and low-liquidity threshold.

**Example**:

```bash
agent-risk-firewall policy --profile balanced
```

### Run a local self-test

```bash
agent-risk-firewall self-test
```

**When to use**: Run this after installation or before submitting a PR to verify that the CLI, policy engine, and JSON renderer work without live assets or external scans.

**Output**: JSON with `status: pass` or `status: fail` plus three fixture verdicts for allow, warn, and block cases.

**Example**:

```bash
agent-risk-firewall self-test
```

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `INVALID_JSON` | Input is not valid JSON | Fix the input file or stdin payload. |
| `INVALID_INPUT` | Required fields are missing or malformed | Add `chain`, `operation`, `walletAddress`, token context, and quote/tx details. |
| `ONCHAINOS_UNAVAILABLE` | The `onchainos` CLI is not installed | Install `okx/onchainos-skills`, then retry. |
| `SCAN_TIMEOUT` | A live OKX scan timed out | Retry once; if still unavailable, treat the result as incomplete verification. |
| `UNSUPPORTED_CHAIN` | Chain is outside MVP scope | Use `xlayer` or `solana`. |

## Security Notices

- This plugin never asks for, stores, or handles private keys or seed phrases.
- This plugin never signs or broadcasts transactions.
- This plugin is a guardrail, not a guarantee of safety. Onchain data, external APIs, and simulations can be incomplete or stale.
- Do not override a `block` verdict. A `block` means the agent must cancel the proposed operation.
- `warn` requires explicit user confirmation before signing.
- Trading and DeFi activity can cause loss of funds. Use dry-run and small amounts first.
