"""Keep shared evidence stable and omit only catalog-backed quote duplicates."""
import hashlib
import json
from typing import Any

DYNAMIC_SECTION = "\n[현재 토론 상태 JSON]\n"
ROLE_SECTION = "\n\n[이번 호출의 역할]\n"


def with_role(input_text: str, role: str) -> str:
    """Select the role after the shared input so every call keeps the same cacheable beginning.

    The role goes before the debate-state JSON when there is one, so the JSON stays last.
    """
    head, separator, state = input_text.rpartition(DYNAMIC_SECTION)
    if not separator:
        return input_text + ROLE_SECTION + role
    return head + ROLE_SECTION + role + separator + state


def debate_cache_key(common_input: str) -> str:
    """Route calls that share one debate input to the same prompt cache."""
    return "mc-debate-" + hashlib.sha256(common_input.encode("utf-8")).hexdigest()[:32]


def debate_payload(common_input: str, dynamic: dict[str, Any], catalog: list[dict[str, Any]]) -> str:
    quotes: dict[tuple[str, str], set[str]] = {}
    # A separately supplied catalog must also be present in the actual model input.
    if catalog and json.dumps(catalog, ensure_ascii=False, indent=2, default=str) in common_input:
        for source in catalog:
            for quote in source.get("quotes", []):
                key = (source.get("source_id"), quote.get("quote_id"))
                text = quote.get("text")
                if all(isinstance(value, str) and value for value in (*key, text)):
                    quotes.setdefault(key, set()).add(text)

    def compact(value: Any) -> Any:
        if isinstance(value, dict):
            key = (value.get("source_id"), value.get("quote_id"))
            duplicate = all(isinstance(identifier, str) for identifier in key) and isinstance(value.get("exact_quote"), str) and quotes.get(key) == {value["exact_quote"]}
            return {name: compact(item) for name, item in value.items() if name != "exact_quote" or not duplicate}
        if isinstance(value, list):
            return [compact(item) for item in value]
        return value

    return common_input + DYNAMIC_SECTION + json.dumps(compact(dynamic), ensure_ascii=False, separators=(",", ":"), default=str)
