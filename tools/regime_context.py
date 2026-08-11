import json
from typing import Any


def regime_context_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": analysis.get("schema_version", 1),
        "methodology": analysis.get("methodology", {}),
        "regimes": analysis.get("regimes", {}),
        "comparison": analysis.get("comparison", []),
        "reasons": analysis.get("reasons", {}),
        "limitations": analysis.get("limitations", []),
    }


def build_regime_context(analysis: dict[str, Any]) -> str:
    return json.dumps(
        regime_context_payload(analysis),
        ensure_ascii=False,
        indent=2,
        default=str,
    )
