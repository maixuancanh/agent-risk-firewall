# Agent Risk Firewall

## Overview

Agent Risk Firewall is a pre-trade guardrail for Agentic Wallet swaps on X Layer and Solana. It receives a proposed intent, quote, and transaction context, runs available OKX OnchainOS checks, applies a deterministic balanced policy, and returns `allow`, `warn`, or `block`.

Core operations:

- Check proposed swaps, token buys, token sells, and approvals before signing
- Normalize OKX security scan, transaction scan, token report, and simulation evidence
- Return deterministic `allow`, `warn`, or `block` verdicts for agent workflows

Tags: `security` `risk` `agentic-wallet` `xlayer` `solana` `trading`

## Prerequisites

- No IP restrictions enforced by this plugin
- Supported chains: X Layer and Solana
- Supported operations: swaps, token buys, token sells, and approvals
- Python 3.8+
- Optional for live checks: `npx skills add okx/onchainos-skills`
- Optional for production reliability: personal OKX OnchainOS API credentials configured in the environment

## Quick Start

1. **Prepare a request**: Build a JSON payload with `chain`, `operation`, wallet address, token context, quote details, and optional transaction context.
2. **Run the firewall**: Execute `agent-risk-firewall check --input request.json --format json` before asking the user to sign.
3. **Apply the verdict**: Continue on `allow`, ask explicit confirmation on `warn`, and cancel the operation on `block`.
4. **Inspect policy or installation**: Use `agent-risk-firewall policy --profile balanced` to view thresholds and `agent-risk-firewall self-test` to verify local installation.

The plugin does not sign, broadcast, trade, revoke approvals, or handle private keys.
