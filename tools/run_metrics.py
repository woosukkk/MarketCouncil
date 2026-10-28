"""Local, allowlisted measurements; never retain prompts, responses or credentials."""
import json
import math
import os
import platform
import re
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


STAGE_NAMES = frozenset({
    "collect", "financial_data", "valuation", "filing_search", "bull_report_search",
    "bear_report_search", "report_context", "web_collection", "source_classification",
    "evidence_resolution", "web_context", "history", "regime", "regime_reasons",
    "bull_initial", "bear_initial", "sentiment", "shorts", "video_topics",
    "video_summary", "create_agenda", "bull_turn", "bear_turn", "moderator_review",
    "summarize", "navigation",
})
API_PHASES = frozenset({
    "source_collection", "bull_initial", "bear_initial", "regime_reasons",
    "shorts_debate_topics", "video_summary", "debate_navigation", "debate_agenda",
    "debate_review", "debate_summary", "bull_debate_turn", "bear_debate_turn",
    "report_source_collection", "bull_web_search", "bear_web_search",
})
_ACTIVE: ContextVar[Any] = ContextVar("analysis_measurements", default=None)
_MODEL = re.compile(r"(?:gpt-|chatgpt-|o[1-9])[a-z0-9][a-z0-9._-]{0,100}\Z")
_DEFAULT_PRICING = Path(__file__).resolve().parent.parent / "benchmarks" / "openai-pricing-2026-10-27.json"


def _integer(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 10**12 else None


def _field(obj: Any, key: str) -> Any:
    try:
        return obj.get(key) if isinstance(obj, dict) else getattr(obj, key, None)
    except Exception:
        return None


def _pricing(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict) or value.get("currency") != "USD":
        return None
    model, source, as_of = value.get("model"), value.get("source"), value.get("as_of")
    if not isinstance(model, str) or not _MODEL.fullmatch(model) or source not in {"openai_api_pricing", "manual"}:
        return None
    try:
        if not isinstance(as_of, str) or date.fromisoformat(as_of).isoformat() != as_of:
            return None
    except ValueError:
        return None
    rates = {}
    for key in ("input_per_million", "cached_input_per_million", "output_per_million"):
        number = value.get(key)
        if type(number) not in (int, float) or not 0 <= number <= 10**6 or not math.isfinite(number):
            return None
        rates[key] = number
    if rates["cached_input_per_million"] > rates["input_per_million"]:
        return None
    return {"model": model, "currency": "USD", "source": source, "as_of": as_of, **rates}


def _load_pricing(value: Any) -> dict[str, Any] | None:
    try:
        if value is not None:
            return _pricing(value)
        path = Path(os.environ["RESULTS_PRICING_FILE"]) if "RESULTS_PRICING_FILE" in os.environ else _DEFAULT_PRICING
        if path.stat().st_size > 16384:
            return None
        return _pricing(json.loads(path.read_text(encoding="utf-8-sig")))
    except Exception:
        return None


class _Measurements:
    def __init__(self, pricing: dict[str, Any] | None) -> None:
        self.pricing = pricing
        self.lock = threading.Lock()
        self.stages: list[dict[str, Any]] = []
        self.stages_truncated = False
        self.calls: list[dict[str, Any]] = []

    def stage(self, name: str, duration_ms: float, failed: bool = False, cached: bool = False) -> None:
        if name not in STAGE_NAMES:
            return
        row = {"name": name, "duration_ms": max(0.0, duration_ms), "status": "failed" if failed else "success", "cached": cached}
        with self.lock:
            if len(self.stages) >= 1000:
                self.stages_truncated = True
            else:
                self.stages.append(row)

    def response(self, phase: str, kwargs: dict[str, Any], response: Any, failed: bool, duration_ms: float) -> None:
        # Read a fixed set of provider usage fields; never copy kwargs or output_text.
        status = _field(response, "status")
        failed = failed or isinstance(status, str) and status != "completed"
        usage = _field(response, "usage")
        input_tokens, output_tokens = _integer(_field(usage, "input_tokens")), _integer(_field(usage, "output_tokens"))
        input_details, output_details = _field(usage, "input_tokens_details"), _field(usage, "output_tokens_details")
        cached = _integer(_field(input_details, "cached_tokens"))
        raw_reasoning = _field(output_details, "reasoning_tokens")
        reasoning = _integer(raw_reasoning)
        invalid_reasoning = raw_reasoning is not None and (reasoning is None or output_tokens is not None and reasoning > output_tokens)
        if input_tokens is None or cached is not None and cached > input_tokens:
            cached = None
        if output_tokens is None or reasoning is not None and reasoning > output_tokens:
            reasoning = None
        requested_model = kwargs.get("model")
        model = requested_model if isinstance(requested_model, str) and _MODEL.fullmatch(requested_model) else None
        response_tier = _field(response, "service_tier")
        tier = response_tier if response_tier is not None else kwargs.get("service_tier")
        cache_write = _field(input_details, "cache_write_tokens")
        known = input_tokens is not None and output_tokens is not None
        cost = None
        rates = self.pricing
        if known and cached is not None and rates and model == rates["model"] and tier in (None, "default", "standard", "auto") and not cache_write and not invalid_reasoning:
            # Reasoning is part of output_tokens, not a second charge.
            cost = ((input_tokens - cached) * rates["input_per_million"] + cached * rates["cached_input_per_million"] + output_tokens * rates["output_per_million"]) / 10**6
        row = {"id": uuid.uuid4().hex, "phase": phase if phase in API_PHASES else "unclassified", "model": model,
               "input": input_tokens, "output": output_tokens, "cached": cached, "reasoning": reasoning,
               "known": known, "failed": failed, "cost": cost, "tools": bool(kwargs.get("tools")), "duration_ms": max(0.0, duration_ms)}
        with self.lock:
            self.calls.append(row)

    @staticmethod
    def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
        known = [row for row in rows if row["known"]]
        priced = [row for row in rows if row["cost"] is not None]
        models = {row["model"] for row in rows}
        complete_cost = bool(rows) and len(priced) == len(rows) and len(models) == 1 and None not in models and not any(row["tools"] for row in rows)
        return {
            "request_count": len(rows), "error_count": sum(row["failed"] for row in rows),
            "usage_known_calls": len(known), "usage_missing_calls": len(rows) - len(known),
            "input_tokens": sum(row["input"] for row in known) if known else None,
            "output_tokens": sum(row["output"] for row in known) if known else None,
            "cached_input_tokens": sum(row["cached"] for row in rows) if rows and len(known) == len(rows) and all(row["cached"] is not None for row in rows) else None,
            "reasoning_tokens": sum(row["reasoning"] for row in rows) if rows and len(known) == len(rows) and all(row["reasoning"] is not None for row in rows) else None,
            "estimated_cost_usd": sum(row["cost"] for row in priced) if priced else None,
            "cost_status": "estimated" if complete_cost else "partial" if priced else "unavailable",
            "model": next(iter(models)) if len(models) == 1 else None,
        }

    def report(self) -> dict[str, Any]:
        with self.lock:
            rows = list(self.calls)
            stages = list(self.stages)
            truncated = self.stages_truncated
        llm = {
            **self.summarize(rows),
            "coverage": "observed_responses_only", "sdk_retries_included": False, "tool_costs_included": False,
            "pricing": self.pricing,
            "by_phase": [{"phase": phase, **self.summarize([row for row in rows if row["phase"] == phase]),
                          "duration_ms": sum(row["duration_ms"] for row in rows if row["phase"] == phase)}
                         for phase in sorted({row["phase"] for row in rows})],
        }
        return {"stages": stages, "stages_truncated": truncated, "llm": llm}


@contextmanager
def measure_stage(name: str) -> Iterator[None]:
    collector = _ACTIVE.get()
    started, failed = time.perf_counter(), False
    try:
        yield
    except BaseException:
        failed = True
        raise
    finally:
        if collector is not None:
            try:
                collector.stage(name, (time.perf_counter() - started) * 1000, failed)
            except Exception:
                pass


def record_cached_stage(name: str, duration_ms: float) -> None:
    collector = _ACTIVE.get()
    if collector is None:
        return
    # Checkpoint round suffixes are numeric only; arbitrary labels stay private.
    try:
        if not isinstance(name, str):
            return
        stage = re.sub(r"-\d+$", "", name)
        collector.stage(stage, duration_ms, cached=True)
    except Exception:
        pass


def create_response(client: Any, phase: str, **kwargs: Any) -> Any:
    collector = _ACTIVE.get()
    response, failed = None, False
    started = time.perf_counter()
    try:
        response = client.responses.create(**kwargs)
        return response
    except BaseException:
        failed = True
        raise
    finally:
        if collector is not None:
            try:
                collector.response(phase, kwargs, response, failed, (time.perf_counter() - started) * 1000)
            except Exception:
                pass


def measure_analysis(company: str, run: Callable[[], Any], folder: Path, *, pricing: dict[str, Any] | None = None) -> Any:
    started, cpu = time.perf_counter(), time.process_time()
    collector = _Measurements(_load_pricing(pricing))
    token = _ACTIVE.set(collector)
    version = "source"
    if getattr(sys, "frozen", False):
        from desktop.preferences import VERSION
        version = "desktop-v" + VERSION
    report = {"schema_version": 1, "kind": "monitoring", "id": str(uuid.uuid4()), "recorded_at": datetime.now(timezone.utc).isoformat(), "label": company, "version": version, "scope": "analysis", "status": "success", "metrics": {}, "environment": {"os": platform.system(), "python": platform.python_version(), "cpu_count": os.cpu_count()}}
    try:
        return run()
    except BaseException:
        report["status"] = "failed"
        raise
    finally:
        _ACTIVE.reset(token)
        report["metrics"] = {"duration_ms": (time.perf_counter() - started) * 1000, "cpu_ms": (time.process_time() - cpu) * 1000}
        try:
            report.update(collector.report())
            folder.mkdir(parents=True, exist_ok=True)
            (folder / (report["id"] + ".json")).write_text(json.dumps(report, ensure_ascii=False, allow_nan=False), encoding="utf-8")
            print("성능 기록: " + str(folder / (report["id"] + ".json")))
        except Exception:
            # Measurement failure must preserve the analysis result or original error.
            try:
                print("성능 기록 저장 실패 · 분석 결과는 유지됩니다.")
            except Exception:
                pass
