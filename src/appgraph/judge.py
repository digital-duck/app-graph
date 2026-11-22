"""The LLM-as-judge behind `appgraph drift --mode semantic`: one model call per drift dimension, through dd-llm.

One call, so a plain function, not a GraphLang recipe (GraphLang's own rule: no graph for a single model call). The
prompt is prompts/intent_drift.md (graph-code's spl/compute_intent_drift.spl, unchanged); the reply must be one number.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, Optional

PROMPT = Path(__file__).parent / "prompts" / "intent_drift.md"


class JudgeError(RuntimeError):
    pass


def judge_prompt(dimension: str, text_a: str, text_b: str) -> str:
    return (PROMPT.read_text().replace("{{dimension}}", dimension)
            .replace("{{intent_a}}", text_a).replace("{{intent_b}}", text_b))


def parse_score(reply: str, dimension: str = "") -> float:
    match = re.search(r"\d*\.?\d+", reply.strip())
    if not match:
        raise JudgeError(f"could not parse a {dimension} drift score from the model's reply: {reply.strip()[:200]!r}")
    return float(match.group())


def make_judge(llm: str, timeout: Optional[int] = None, max_output_tokens: Optional[int] = None,
               adapter_factory: Optional[Callable] = None) -> Callable[[str, str, str], float]:
    """A (dimension, text_a, text_b) -> float callable for graph_lib.drift_report(judge=...). `llm` is ADAPTER[:MODEL].
    max_output_tokens matters for reasoning models (ollama:gemma4 spent a small budget thinking and answered nothing)."""
    from dd_llm import get_adapter, parse_llm_spec
    name, model = parse_llm_spec(llm)
    factory = adapter_factory or get_adapter
    adapter = factory(name, **({"timeout": timeout} if timeout else {}))

    def judge(dimension: str, text_a: str, text_b: str) -> float:
        kwargs = {"max_tokens": max_output_tokens} if max_output_tokens else {}
        result = adapter.call(judge_prompt(dimension, text_a, text_b), model=model or "", **kwargs)
        if not result.success:
            errors = result.error_history or []
            raise JudgeError(f"{dimension} drift call failed: {errors[-1]['error'] if errors else 'no reply'}")
        return parse_score(result.content, dimension)

    return judge
