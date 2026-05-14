from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

from .models import target_token


VERDICT_PRIORITY = {"allow": 0, "warn": 1, "block": 2}


BALANCED_POLICY = {
    "profile": "balanced",
    "supportedChains": ["xlayer", "solana"],
    "maxTradeUsd": 250,
    "maxWalletPct": 10,
    "slippageWarnPct": 2,
    "slippageBlockPct": 5,
    "priceImpactWarnPct": 3,
    "priceImpactBlockPct": 8,
    "lowLiquidityUsd": 10000,
}


def get_policy(profile: str = "balanced") -> Dict[str, Any]:
    if profile != "balanced":
        return dict(BALANCED_POLICY, requestedProfile=profile, warning="Unknown profile; using balanced.")
    return dict(BALANCED_POLICY)


def evaluate(
    context: Dict[str, Any],
    evidence: Dict[str, Any],
    validation_findings: Optional[List[Dict[str, Any]]] = None,
    profile: str = "balanced",
) -> Dict[str, Any]:
    policy = get_policy(profile)
    reasons: List[Dict[str, Any]] = []
    for finding in validation_findings or []:
        _add_reason(reasons, finding)

    _evaluate_amount_caps(context, policy, reasons)
    _evaluate_quote(context, policy, reasons)
    _evaluate_token_scan(context, evidence.get("tokenScan") or {}, reasons)
    _evaluate_token_report(evidence.get("tokenReport") or {}, policy, reasons)
    _evaluate_tx_scan(context, evidence.get("txScan") or {}, reasons)
    _evaluate_simulation(context, evidence.get("simulation") or {}, reasons)

    verdict = _highest_verdict(reasons)
    risk_score = _risk_score(reasons, verdict)
    return {
        "verdict": verdict,
        "riskScore": risk_score,
        "requiresUserConfirmation": verdict == "warn",
        "reasons": _public_reasons(reasons),
        "evidence": evidence,
        "safeNextStep": _safe_next_step(verdict),
    }


def _evaluate_amount_caps(context: Dict[str, Any], policy: Dict[str, Any], reasons: List[Dict[str, Any]]) -> None:
    amount_usd = context.get("amountInUsd")
    wallet_value_usd = context.get("walletValueUsd")
    if isinstance(amount_usd, Decimal):
        if amount_usd > Decimal(str(policy["maxTradeUsd"])):
            _add_reason(
                reasons,
                {
                    "code": "TRADE_CAP_EXCEEDED",
                    "severity": "block",
                    "score": 88,
                    "message": "Trade amount exceeds the balanced policy per-trade cap.",
                },
            )
        if isinstance(wallet_value_usd, Decimal) and wallet_value_usd > 0:
            pct = (amount_usd / wallet_value_usd) * Decimal("100")
            if pct > Decimal(str(policy["maxWalletPct"])):
                _add_reason(
                    reasons,
                    {
                        "code": "WALLET_EXPOSURE_HIGH",
                        "severity": "block",
                        "score": 86,
                        "message": "Trade amount exceeds 10% of wallet value.",
                    },
                )


def _evaluate_quote(context: Dict[str, Any], policy: Dict[str, Any], reasons: List[Dict[str, Any]]) -> None:
    quote = context.get("quote") or {}
    slippage = _to_decimal(quote.get("slippagePct"))
    price_impact = _to_decimal(quote.get("priceImpactPct"))

    if slippage is not None:
        if slippage > Decimal(str(policy["slippageBlockPct"])):
            _add_reason(
                reasons,
                {
                    "code": "SLIPPAGE_HIGH",
                    "severity": "block",
                    "score": 84,
                    "message": "Quoted slippage is above the balanced policy block threshold.",
                },
            )
        elif slippage >= Decimal(str(policy["slippageWarnPct"])):
            _add_reason(
                reasons,
                {
                    "code": "SLIPPAGE_ELEVATED",
                    "severity": "warn",
                    "score": 58,
                    "message": "Quoted slippage is elevated.",
                },
            )

    if price_impact is not None:
        if price_impact > Decimal(str(policy["priceImpactBlockPct"])):
            _add_reason(
                reasons,
                {
                    "code": "PRICE_IMPACT_HIGH",
                    "severity": "block",
                    "score": 85,
                    "message": "Quoted price impact is above the balanced policy block threshold.",
                },
            )
        elif price_impact >= Decimal(str(policy["priceImpactWarnPct"])):
            _add_reason(
                reasons,
                {
                    "code": "PRICE_IMPACT_ELEVATED",
                    "severity": "warn",
                    "score": 57,
                    "message": "Quoted price impact is elevated.",
                },
            )


def _evaluate_token_scan(context: Dict[str, Any], token_scan: Dict[str, Any], reasons: List[Dict[str, Any]]) -> None:
    token = target_token(context)
    token_needs_scan = bool(isinstance(token, dict) and token.get("address"))
    status = token_scan.get("status")
    data = token_scan.get("data") if isinstance(token_scan.get("data"), dict) else token_scan
    risk_level = str(_dig(data, ["riskLevel", "risk_level", "level"]) or "").upper()
    operation = context.get("operation")

    if token_needs_scan and status in ("unavailable", "timeout", "error"):
        _add_reason(
            reasons,
            {
                "code": "SCAN_UNAVAILABLE" if status != "timeout" else "SCAN_TIMEOUT",
                "severity": "warn",
                "score": 62,
                "message": "Token security scan did not complete; verification is incomplete.",
            },
        )
        return

    if not risk_level:
        return

    if risk_level == "CRITICAL":
        if operation == "sell":
            _add_reason(
                reasons,
                {
                    "code": "TOKEN_CRITICAL_SELL",
                    "severity": "warn",
                    "score": 70,
                    "message": "Target token has CRITICAL risk; selling may be an exit but requires confirmation.",
                },
            )
        else:
            _add_reason(
                reasons,
                {
                    "code": "TOKEN_CRITICAL",
                    "severity": "block",
                    "score": 96,
                    "message": "Target token has CRITICAL risk.",
                },
            )
    elif risk_level == "HIGH":
        _add_reason(
            reasons,
            {
                "code": "TOKEN_HIGH",
                "severity": "warn",
                "score": 68,
                "message": "Target token has HIGH risk.",
            },
        )
    elif risk_level == "MEDIUM":
        _add_reason(
            reasons,
            {
                "code": "TOKEN_MEDIUM",
                "severity": "warn",
                "score": 55,
                "message": "Target token has MEDIUM risk.",
            },
        )


def _evaluate_token_report(token_report: Dict[str, Any], policy: Dict[str, Any], reasons: List[Dict[str, Any]]) -> None:
    if token_report.get("status") != "ok":
        return
    liquidity = _find_numeric(token_report.get("data"), ("liquidityUsd", "liquidityUSD", "liquidity", "totalLiquidity"))
    if liquidity is not None and liquidity < Decimal(str(policy["lowLiquidityUsd"])):
        _add_reason(
            reasons,
            {
                "code": "LIQUIDITY_LOW",
                "severity": "warn",
                "score": 56,
                "message": "Token liquidity appears low for a retail swap.",
            },
        )


def _evaluate_tx_scan(context: Dict[str, Any], tx_scan: Dict[str, Any], reasons: List[Dict[str, Any]]) -> None:
    if not _has_tx(context):
        return
    status = tx_scan.get("status")
    data = tx_scan.get("data") if isinstance(tx_scan.get("data"), dict) else tx_scan
    action = str(_dig(data, ["action", "riskAction", "verdict"]) or "").lower()

    if status in ("unavailable", "timeout", "error"):
        _add_reason(
            reasons,
            {
                "code": "TX_SCAN_UNAVAILABLE" if status != "timeout" else "TX_SCAN_TIMEOUT",
                "severity": "warn",
                "score": 64,
                "message": "Transaction security scan did not complete; verification is incomplete.",
            },
        )
        return

    if action == "block":
        _add_reason(
            reasons,
            {
                "code": "TX_SCAN_BLOCK",
                "severity": "block",
                "score": 98,
                "message": "OKX transaction scan returned a block action.",
            },
        )
    elif action == "warn":
        _add_reason(
            reasons,
            {
                "code": "TX_SCAN_WARN",
                "severity": "warn",
                "score": 72,
                "message": "OKX transaction scan returned a warning.",
            },
        )


def _evaluate_simulation(context: Dict[str, Any], simulation: Dict[str, Any], reasons: List[Dict[str, Any]]) -> None:
    if not _has_tx(context):
        return
    status = simulation.get("status")
    data = simulation.get("data") if isinstance(simulation.get("data"), dict) else simulation

    if status in ("unavailable", "timeout", "error"):
        _add_reason(
            reasons,
            {
                "code": "SIMULATION_UNAVAILABLE" if status != "timeout" else "SIMULATION_TIMEOUT",
                "severity": "warn",
                "score": 63,
                "message": "Transaction simulation did not complete; verification is incomplete.",
            },
        )
        return

    if _simulation_reverted(data):
        _add_reason(
            reasons,
            {
                "code": "SIMULATION_REVERT",
                "severity": "block",
                "score": 94,
                "message": "Transaction simulation indicates the transaction may revert or fail.",
            },
        )


def _simulation_reverted(data: Any) -> bool:
    if isinstance(data, dict):
        explicit = _dig(data, ["success", "succeeded", "isSuccess"])
        if explicit is False:
            return True
        status = str(_dig(data, ["status", "state", "result"]) or "").lower()
        if status in ("failed", "fail", "reverted", "revert", "error"):
            return True
        if _dig(data, ["revertReason", "revert_reason", "error", "errorMessage"]):
            return True
        for value in data.values():
            if _simulation_reverted(value):
                return True
    elif isinstance(data, list):
        return any(_simulation_reverted(item) for item in data)
    elif isinstance(data, str):
        lowered = data.lower()
        return "revert" in lowered or "execution failed" in lowered
    return False


def _has_tx(context: Dict[str, Any]) -> bool:
    tx = context.get("tx") or {}
    return bool(tx.get("to") or tx.get("data") or tx.get("signedTx") or tx.get("signaturePayload"))


def _highest_verdict(reasons: Iterable[Dict[str, Any]]) -> str:
    verdict = "allow"
    for reason in reasons:
        severity = reason.get("severity", "allow")
        if VERDICT_PRIORITY.get(severity, 0) > VERDICT_PRIORITY[verdict]:
            verdict = severity
    return verdict


def _risk_score(reasons: List[Dict[str, Any]], verdict: str) -> int:
    if not reasons:
        return 5
    score = max(int(reason.get("score", 0)) for reason in reasons)
    if verdict == "block":
        return max(score, 80)
    if verdict == "warn":
        return max(score, 50)
    return min(score, 20)


def _safe_next_step(verdict: str) -> str:
    if verdict == "block":
        return "Cancel the operation. Do not ask the user to sign or broadcast this transaction."
    if verdict == "warn":
        return "Show the warning reasons and ask the user for explicit confirmation before signing."
    return "Proceed with the normal signing or broadcast flow if the user already requested it."


def _public_reasons(reasons: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    return [
        {
            "code": str(reason.get("code")),
            "severity": str(reason.get("severity")),
            "message": str(reason.get("message")),
        }
        for reason in reasons
    ]


def _add_reason(reasons: List[Dict[str, Any]], reason: Dict[str, Any]) -> None:
    code = reason.get("code")
    if any(existing.get("code") == code and existing.get("message") == reason.get("message") for existing in reasons):
        return
    reasons.append(reason)


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _dig(data: Any, keys: Iterable[str]) -> Any:
    if isinstance(data, dict):
        for key in keys:
            if key in data:
                return data[key]
        for value in data.values():
            found = _dig(value, keys)
            if found is not None:
                return found
    elif isinstance(data, list):
        for value in data:
            found = _dig(value, keys)
            if found is not None:
                return found
    return None


def _find_numeric(data: Any, keys: Iterable[str]) -> Optional[Decimal]:
    found = _dig(data, keys)
    if found is None:
        return None
    return _to_decimal(found)
