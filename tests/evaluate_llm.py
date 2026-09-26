#!/usr/bin/env python3
"""LLM benchmark evaluator for Indian tax calculator.

Feeds generated test cases to LLMs via three methods (zero-shot, script,
tool-call), scores outputs against ground truth, and produces CSV reports.

Usage:
    python3 tests/evaluate_llm.py                                  # zero-shot, all models
    python3 tests/evaluate_llm.py --method tool-call
    python3 tests/evaluate_llm.py --method script --model "openai/gpt-oss-120b:free"
    python3 tests/evaluate_llm.py --method tool-call --max-rounds 30
"""

import argparse
import csv
import glob
import itertools
import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
GENERATED_DIR = SCRIPT_DIR / "generated"
PROMPT_FILE = SCRIPT_DIR / "prompts" / "system_prompt.txt"
CHECKPOINT_DIR = SCRIPT_DIR / "evaluation_checkpoints"
RESULTS_DIR = SCRIPT_DIR / "evaluation_results"
LOGS_DIR = SCRIPT_DIR / "evaluation_logs"

# ---------------------------------------------------------------------------
# API & retry constants
# ---------------------------------------------------------------------------
MAX_OUTPUT_TOKENS = None
MAX_TRANSIENT_RETRIES = 3 # overridable with CLI
COST_CHECK_INTERVAL = 5
FREE_COOLDOWN_SECS = 120
FREE_COOLDOWN_MAX_RETRIES = 2
API_TIMEOUT_SECS = 600  # per-attempt request timeout; without this a stuck
                         # provider blocks the case (and its concurrency slot)
                         # forever, as observed with nemotron-3-ultra hanging
                         # 20+ min on a single request. 600s gives ~2x headroom
                         # over the slowest model's observed average latency
                         # (hy3-preview, 336s/case) so a legitimately slow but
                         # working reasoning model isn't cut off mid-response,
                         # while still failing well before a genuine hang.
EMPTY_COMPLETION_RETRIES = 2  # a 200 OK with 0 completion tokens is a distinct
                               # failure mode from a 429/503 — api_call_with_retry
                               # treats it as success since the HTTP call itself
                               # succeeded, so it's never retried by that logic.
                               # Observed on nemotron-3-ultra: whole stretches of
                               # cases coming back with genuinely empty content,
                               # burning scarce daily-cap requests on 0-score
                               # PARSE_FAILs instead of a real answer.

# ---------------------------------------------------------------------------
# Evaluation defaults (overridable via CLI)
# ---------------------------------------------------------------------------
MAX_TOOL_ROUNDS = 20
MAX_SCRIPT_RETRIES = 3
SCRIPT_TIMEOUT = 20
TOLERANCE = 0.01
DELAY_BETWEEN_CASES = 1.0
CONSECUTIVE_SKIP_LIMIT = 5
MAX_CASES = 500

# ---------------------------------------------------------------------------
# Models & per-model config
# ---------------------------------------------------------------------------
MODELS = [
    # Strong
    "openai/gpt-oss-120b",
    "tencent/hy3-preview:free",
    # Mid
    "deepseek/deepseek-chat-v3-0324",
    "meta-llama/llama-3.3-70b-instruct",
    "google/gemma-4-31b-it:free",
    # Weak
    "openai/gpt-oss-20b",
    "nvidia/nemotron-nano-9b-v2:free",
    # "qwen/qwen3.5-9b",
]

MODEL_CONFIG = {
    # Free models: conservative to avoid 429 storms
    "tencent/hy3-preview:free":          {"rpm": 20, "concurrency": 8},
    "google/gemma-4-31b-it:free":        {"rpm": 12, "concurrency": 4},
    "nvidia/nemotron-nano-9b-v2:free":   {"rpm": 20, "concurrency": 8},
    # Paid models: push harder
    "openai/gpt-oss-120b":               {"rpm": 25, "concurrency": 8},
    "openai/gpt-oss-20b":                {"rpm": 25, "concurrency": 8},
    "deepseek/deepseek-chat-v3-0324":    {"rpm": 25, "concurrency": 8},
    "meta-llama/llama-3.3-70b-instruct": {"rpm": 25, "concurrency": 8},
    "qwen/qwen3.5-9b":                   {"rpm": 25, "concurrency": 8},
    # Gemini (direct, not via OpenRouter) — this key's actual free-tier burst
    # tolerance is much lower than the nominal 10 rpm; concurrency=3 tripped
    # 429s immediately in testing, so start conservative (single in-flight).
    "gemini-3.8-flash":                  {"rpm": 4, "concurrency": 1},
    # Local Ollama — no quota and no cost, so the only limit is the machine.
    # concurrency stays at 1: local generation is memory-bandwidth-bound, so
    # parallel requests split the same bandwidth instead of adding throughput.
    # reasoning_effort="none" suppresses the thinking trace, which otherwise
    # consumes most of the context and dominates runtime: 277 -> 41 completion
    # tokens (34.0s -> 6.0s) on an identical probe prompt. The benchmark scores
    # 37 numeric answer fields, not reasoning quality, and it makes this model
    # comparable to the non-reasoning models already in the table.
    "ollama/gemma4-12b-ctx8k":           {"rpm": 600, "concurrency": 1,
                                          "reasoning_effort": "none"},
    # Same weights at num_ctx 16384, for the script method only: a generated tax
    # script runs ~2,500 tokens, and a retry round must also carry the previous
    # script in full plus the traceback, which does not fit in 8192.
    "ollama/gemma4-12b-ctx16k":          {"rpm": 600, "concurrency": 1,
                                          "reasoning_effort": "none"},
}

FREE_FALLBACKS = {
    "google/gemma-4-31b-it:free": "google/gemma-4-31b-it",
}

DEFAULT_MODEL_CONFIG = {"rpm": 12, "concurrency": 4}
DEFAULT_BUDGET = 17.00  # USD — max spend before halting

# ---------------------------------------------------------------------------
# Scored field definitions (37 fields)
# ---------------------------------------------------------------------------
SALARY_FIELDS = [
    ("gross_salary", ("Under Head Salaries", "Gross Salary")),
    ("sec_10_13a", ("Under Head Salaries", "Exemptions", "Section 10(13A)")),
    ("sec_10_5", ("Under Head Salaries", "Exemptions", "Section 10(5)")),
    ("sec_16_ia", ("Under Head Salaries", "Section 16(ia)")),
    ("sec_16_ii", ("Under Head Salaries", "Section 16(ii)")),
    ("sec_16_iii", ("Under Head Salaries", "Section 16(iii)")),
    ("net_salary", ("Under Head Salaries", "Net Salary")),
]

OTHER_SOURCES_FIELDS = [
    ("savings_bank_interest", ("Income from Other Sources", "Savings Bank Interest")),
    ("deposit_interest", ("Income from Other Sources", "Deposit Interest")),
    ("epf_taxable_interest", ("Income from Other Sources", "Other Interest", "EPF Taxable Interest")),
]

AGGREGATE_FIELDS = [
    ("gross_total_income", ("Gross Total Income",)),
    ("total_taxable_income", ("Total Taxable Income",)),
]

DEDUCTION_LEAF_FIELDS = [
    ("80ccd_1b", ("Deductions", "80CCD(1B)")),
    ("80ccd_2", ("Deductions", "80CCD(2)")),
    ("80d", ("Deductions", "80D")),
    ("80e", ("Deductions", "80E")),
    ("80g", ("Deductions", "80G")),
    ("80tta", ("Deductions", "80TTA")),
    ("80ttb", ("Deductions", "80TTB")),
    ("total_deductions", ("Deductions", "Total Deductions")),
]

TAX_FIELDS = [
    ("tax_at_slab_rates", ("Tax Computation", "Tax at Slab Rates")),
    ("tax_stcg_111a", ("Tax Computation", "Tax on STCG (Section 111A)")),
    ("tax_stcg_other", ("Tax Computation", "Tax on STCG (Other)")),
    ("tax_ltcg_112a", ("Tax Computation", "Tax on LTCG (Section 112A)")),
    ("tax_ltcg_non_equity", ("Tax Computation", "Tax on LTCG (Non-Equity)")),
    ("tax_ltcg_other", ("Tax Computation", "Tax on LTCG (Other)")),
    ("total_tax_before_rebate", ("Tax Computation", "Total Tax Before Rebate")),
    ("rebate_87a", ("Tax Computation", "Less: Rebate under Section 87A")),
    ("tax_after_rebate", ("Tax Computation", "Tax After Rebate")),
    ("surcharge", ("Tax Computation", "Surcharge")),
    ("cess", ("Tax Computation", "Health and Education Cess")),
    ("total_tax_liability", ("Tax Computation", "Total Tax Liability")),
    ("tds", ("Tax Computation", "Less: TDS")),
    ("net_tax_payable", ("Tax Computation", "Net Tax Payable / Refund")),
]

COMBINED_FIELDS = ["combined_stcg", "combined_ltcg", "80c_80ccc_80ccd1"]

ALL_FIELD_NAMES = (
    [f[0] for f in SALARY_FIELDS]
    + COMBINED_FIELDS[:2]  # combined_stcg, combined_ltcg
    + [f[0] for f in OTHER_SOURCES_FIELDS]
    + [f[0] for f in AGGREGATE_FIELDS]
    + [COMBINED_FIELDS[2]]  # 80c_80ccc_80ccd1
    + [f[0] for f in DEDUCTION_LEAF_FIELDS]
    + [f[0] for f in TAX_FIELDS]
)

SECTION_MAP = {
    "salary": [f[0] for f in SALARY_FIELDS],
    "capital_gains": COMBINED_FIELDS[:2],
    "other_sources": [f[0] for f in OTHER_SOURCES_FIELDS],
    "aggregates": [f[0] for f in AGGREGATE_FIELDS],
    "deductions": [COMBINED_FIELDS[2]] + [f[0] for f in DEDUCTION_LEAF_FIELDS],
    "tax_computation": [f[0] for f in TAX_FIELDS],
}

# ---------------------------------------------------------------------------
# Key normalization lookup (fixes tokenizer-mangled JSON keys)
# ---------------------------------------------------------------------------
_SCHEMA_KEYS = [
    "Under Head Salaries", "Gross Salary", "Exemptions",
    "Section 10(13A)", "Section 10(5)",
    "Section 16(ia)", "Section 16(ii)", "Section 16(iii)",
    "Net Salary", "Capital Gains", "STCG (Section 111A)",
    "STCG (Other)", "LTCG (Section 112A)", "LTCG (Non-Equity)",
    "LTCG (Other)", "Income from Other Sources",
    "Savings Bank Interest", "Deposit Interest", "Other Interest",
    "EPF Taxable Interest", "Gross Total Income", "Deductions",
    "Total Deductions", "Total Taxable Income", "Tax Computation",
    "Bonds", "Debentures", "G-Secs", "Mutual Funds", "Total",
    "80C", "80CCC", "80CCD(1)", "80CCD(1B)", "80CCD(2)",
    "80D", "80E", "80G", "80TTA", "80TTB",
    "Tax at Slab Rates", "Tax on STCG (Section 111A)",
    "Tax on STCG (Other)", "Tax on LTCG (Section 112A)",
    "Tax on LTCG (Non-Equity)", "Tax on LTCG (Other)",
    "Total Tax Before Rebate", "Less: Rebate under Section 87A",
    "Tax After Rebate", "Surcharge", "Health and Education Cess",
    "Total Tax Liability", "Less: TDS", "Net Tax Payable / Refund",
]
_KEY_LOOKUP = {k.replace(" ", "").lower(): k for k in _SCHEMA_KEYS}

# ---------------------------------------------------------------------------
# Tool definition
# ---------------------------------------------------------------------------
CALCULATE_TOOL = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": (
            "Performs arithmetic. Supports: add, subtract, multiply, divide "
            "(floating-point). Operands list can have 2+ values. Operations are "
            "left-associative: subtract(10, 3, 2) = (10-3)-2 = 5. "
            "divide(100, 4, 5) = (100/4)/5 = 5.0. You may request multiple "
            "calculate calls in parallel within a single response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                },
                "operands": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                },
            },
            "required": ["operation", "operands"],
        },
    },
}


# ---------------------------------------------------------------------------
# Data class for case results
# ---------------------------------------------------------------------------
@dataclass
class CaseResult:
    case_file: str
    description: str
    archetype: str  # taxpayer profile ID, e.g. "P01" (empty for pairwise/ota modes)
    model: str
    method: str
    rounds_used: int
    parsed: bool
    llm_output: dict | None
    scores: dict  # field_name -> 0 or 1
    pct_errors: dict  # field_name -> float percentage error
    total_score: int
    total_pct: float
    latency_sec: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    messages: list | None  # conversation transcript for failed/low-score cases


LOCAL_PREFIX = "ollama/"
LOCAL_BASE_URL = "http://localhost:11434/v1"
LOCAL_TIMEOUT_SECS = 3600  # a 12B on consumer hardware can spend >10 min on one
                           # case; there is no provider-hang risk to guard against
                           # locally, so the API_TIMEOUT_SECS ceiling is too tight


def is_local_model(model):
    return bool(model) and model.startswith(LOCAL_PREFIX)


def api_model_name(model):
    """Strip the routing prefix so the request carries the provider's own ID."""
    return model[len(LOCAL_PREFIX):] if is_local_model(model) else model


# ---------------------------------------------------------------------------
# Provider client — OpenRouter for most models, Gemini's own OpenAI-compatible
# endpoint for "gemini-*" model IDs (these aren't available on OpenRouter's
# free tier, so they're evaluated directly against Google's API instead), and a
# local Ollama server for "ollama/*" IDs (no quota, no cost — used for the
# high-request-count method comparison that the free-tier daily cap forbids).
# ---------------------------------------------------------------------------
def get_client(model=None):
    if is_local_model(model):
        return OpenAI(base_url=LOCAL_BASE_URL, api_key="ollama", timeout=LOCAL_TIMEOUT_SECS)
    if model and model.startswith("gemini-"):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: Set GEMINI_API_KEY environment variable.")
            sys.exit(1)
        return OpenAI(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=api_key,
            timeout=API_TIMEOUT_SECS,
        )
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.")
        sys.exit(1)
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key, timeout=API_TIMEOUT_SECS)


class CostGuard:
    def __init__(self, budget=DEFAULT_BUDGET):
        self.budget = budget
        self.cases_since_check = 0
        self.initial_usage = None
        self._lock = threading.Lock()

    def initialize(self):
        """Capture the starting usage from OpenRouter credits endpoint."""
        self.initial_usage = self._fetch_usage()
        if self.initial_usage is not None:
            print(f"  Cost guard: initial usage = ${self.initial_usage:.4f}, budget = ${self.budget:.2f}")

    def case_completed(self):
        """Call after each case completes. Checks balance every N cases."""
        with self._lock:
            self.cases_since_check += 1
            if self.cases_since_check >= COST_CHECK_INTERVAL:
                self.cases_since_check = 0
                self._check_balance()

    def spent(self):
        """Return total spent since start, or None if unknown."""
        if self.initial_usage is None:
            return None
        current = self._fetch_usage()
        if current is None:
            return None
        return current - self.initial_usage

    def _fetch_usage(self):
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            return None
        try:
            result = subprocess.run(
                ["curl", "-s", "https://openrouter.ai/api/v1/credits",
                 "-H", f"Authorization: Bearer {api_key}"],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(result.stdout)
            return float(data["data"]["total_usage"])
        except Exception:
            return None

    def _check_balance(self):
        if self.initial_usage is None:
            return
        current = self._fetch_usage()
        if current is None:
            return
        cost = current - self.initial_usage
        if cost > self.budget:
            raise RuntimeError(
                f"BUDGET EXCEEDED: ${cost:.4f} spent (budget: ${self.budget:.2f}). "
                f"Halting. Use --budget to increase."
            )
        if cost > 0:
            print(f"  [cost guard] ${cost:.4f} spent of ${self.budget:.2f} budget")


_cost_guard = CostGuard()  # re-initialized in main() with --budget value

# ---------------------------------------------------------------------------
# Rate limiter — thread-safe, enforces N requests per minute
# ---------------------------------------------------------------------------
class RateLimiter:
    def __init__(self, requests_per_minute):
        self._interval = 60.0 / requests_per_minute
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_call = time.monotonic()


_checkpoint_lock = threading.Lock()
_print_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Token tracking
# ---------------------------------------------------------------------------
class TokenTracker:
    def __init__(self):
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.cost = 0.0

    def add(self, response):
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        self.prompt_tokens += getattr(usage, "prompt_tokens", 0) or 0
        self.completion_tokens += getattr(usage, "completion_tokens", 0) or 0
        self.cost += float(getattr(usage, "cost", 0) or 0)

    @property
    def total_tokens(self):
        return self.prompt_tokens + self.completion_tokens


# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------
def load_system_prompt():
    if not PROMPT_FILE.exists():
        print(f"ERROR: Prompt file not found: {PROMPT_FILE}")
        sys.exit(1)
    return PROMPT_FILE.read_text().strip()


def build_messages(method, system_prompt, input_json):
    user_content = "Here is the taxpayer input:\n" + json.dumps(input_json, indent=2)
    if method == "script":
        user_content += (
            "\n\nWrite a Python script that reads the input JSON from the file "
            "'input.json' in the current working directory, computes the tax output, "
            "and prints ONLY the output JSON to stdout. "
            "You have access to the Python standard library only."
        )
    elif method == "tool-call":
        # Batching is mandatory, not optional. With one calculate call per round a
        # 37-field return cannot finish inside MAX_ROUNDS: observed 19 sequential
        # single-call rounds still mid-computation at the cutoff, scoring 0.
        user_content += (
            "\n\nUse the calculate tool for ALL arithmetic — never perform mental "
            "math.\n"
            "Batch your calls: group independent calculations into the same "
            "response as several parallel calculate calls, rather than sending "
            "one at a time. Aim for roughly 5-10 calls per response — enough to "
            "make progress, but stop and wait for the results rather than trying "
            "to emit every remaining calculation at once.\n"
            f"You have a budget of {MAX_TOOL_ROUNDS} rounds, so a handful of "
            "moderate batches will comfortably cover a 37-field return. Once you "
            "have the numbers you need, output the final JSON."
        )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------
def get_response_text(message):
    """Extract text from a message, checking content then reasoning fields.

    Reasoning models (Nemotron, GPT-OSS) put chain-of-thought in `reasoning`
    and the final answer in `content`. If `content` is empty/None, fall back
    to `reasoning` (the model may have put everything there).
    """
    text = message.content or ""
    if not text:
        reasoning = getattr(message, "reasoning", None) or ""
        if reasoning:
            text = reasoning
    return text


def _clean_json_text(text):
    """Strip control characters that some models embed in JSON output."""
    return re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f]", "", text)


def _valid_output(obj):
    """Return obj if it's a non-empty dict, else None."""
    return obj if isinstance(obj, dict) and len(obj) > 0 else None


def _normalize_keys(obj):
    """Recursively fix tokenizer-mangled key names."""
    if not isinstance(obj, dict):
        return obj
    normalized = {}
    for k, v in obj.items():
        stripped = k.replace(" ", "").lower()
        correct_key = _KEY_LOOKUP.get(stripped, k)
        normalized[correct_key] = _normalize_keys(v)
    return normalized


def extract_json(text):
    try:
        result = _valid_output(json.loads(text))
        if result is not None:
            return _normalize_keys(result)
    except (json.JSONDecodeError, TypeError):
        pass
    if not text:
        return None
    cleaned = _clean_json_text(text)
    try:
        result = _valid_output(json.loads(cleaned))
        if result is not None:
            return _normalize_keys(result)
    except (json.JSONDecodeError, TypeError):
        pass
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if fenced:
        try:
            result = _valid_output(json.loads(fenced.group(1)))
            if result is not None:
                return _normalize_keys(result)
        except json.JSONDecodeError:
            pass
    # Find the largest valid JSON object (skip trivially small ones like {})
    search_from = 0
    best = None
    while True:
        start = cleaned.find("{", search_from)
        if start == -1:
            break
        depth = 0
        for i in range(start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[start : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            if best is None or len(candidate) > len(json.dumps(best)):
                                best = parsed
                    except json.JSONDecodeError:
                        pass
                    search_from = i + 1
                    break
        else:
            break
    if best is not None:
        return _normalize_keys(best)
    return None


def extract_code(text):
    fenced = re.search(r"```(?:python)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    # Unterminated fence: the response was cut off mid-script, so there is an
    # opening ``` but no closing one. Without this branch the fallback below
    # returned the fence line as part of the code and every such case died with
    # "SyntaxError: invalid syntax" on line 1 instead of surfacing the real
    # problem (a truncated response).
    unterminated = re.search(r"```(?:python)?[^\S\n]*\n(.*)", text, re.DOTALL)
    if unterminated:
        return re.sub(r"\n\s*```[^\S\n]*$", "", unterminated.group(1))
    lines = text.strip().split("\n")
    if any("import" in l or "print" in l or "open(" in l for l in lines):
        return text.strip()
    return None


def execute_calculate(operation, operands):
    result = operands[0]
    for x in operands[1:]:
        if operation == "add":
            result += x
        elif operation == "subtract":
            result -= x
        elif operation == "multiply":
            result *= x
        elif operation == "divide":
            result /= x
    return round(result, 10)


class RateLimitExhausted(Exception):
    """All retries exhausted due to rate limiting (429)."""
    pass


def _is_daily_cap_error(err_str):
    """True if a 429's message indicates a hard per-day quota (no point retrying
    today), as opposed to a transient per-minute rate limit.

    Providers phrase this differently: OpenRouter says "...free-models-per-day"
    (matched by "daily"/"limit exceeded"); Gemini's quotaId is
    "GenerateRequestsPerDayPerProjectPerModel-FreeTier" — no "daily" substring,
    hence the separate normalized "perday" check.
    """
    normalized = err_str.replace("-", "").replace("_", "")
    return "daily" in err_str or "limit exceeded" in err_str or "perday" in normalized


def api_call_with_retry(client, model_delay_state, rate_limiter, **kwargs):
    """Wraps client.chat.completions.create with retry + 429 handling.

    Automatically attempts response_format=json_object first, falls back
    without it if the model/provider doesn't support it.

    Returns the API response.  Raises on non-recoverable errors.
    model_delay_state is a mutable dict: {"consecutive_429": int, "delay": float,
                                          "json_format_supported": bool}
    """
    use_json_format = model_delay_state.get("json_format_supported", False)
    requested_model = kwargs.get("model", "")
    active_model = api_model_name(requested_model)
    reasoning_effort = MODEL_CONFIG.get(requested_model, {}).get("reasoning_effort")
    last_was_rate_limit = False
    model_max_tokens = model_delay_state.get("max_tokens", MAX_OUTPUT_TOKENS)

    for attempt in range(MAX_TRANSIENT_RETRIES):
        rate_limiter.wait()
        call_kwargs = dict(kwargs)
        call_kwargs["model"] = active_model
        if reasoning_effort:
            call_kwargs.setdefault("reasoning_effort", reasoning_effort)
        if model_max_tokens is not None:
            call_kwargs.setdefault("max_tokens", model_max_tokens)
        if use_json_format and "tools" not in call_kwargs:
            call_kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = client.chat.completions.create(**call_kwargs)
            model_delay_state["consecutive_429"] = 0
            return resp
        except Exception as e:
            err_str = str(e).lower()
            status = getattr(e, "status_code", None) or getattr(e, "code", None)

            # response_format not supported — retry without it
            if use_json_format and (status == 400
                                    or "response_format" in err_str
                                    or "json_object" in err_str
                                    or "json mode" in err_str
                                    or "not supported" in err_str
                                    or "unsupported" in err_str
                                    or "none" in err_str):
                model_delay_state["json_format_supported"] = False
                use_json_format = False
                continue

            # Rate limit (429)
            if status == 429 or "429" in err_str or "rate" in err_str:
                last_was_rate_limit = True
                model_delay_state["consecutive_429"] += 1
                if model_delay_state["consecutive_429"] >= 3:
                    model_delay_state["delay"] = min(model_delay_state["delay"] * 2, 120)

                # If a paid fallback exists, switch permanently for this call
                fallback = FREE_FALLBACKS.get(active_model)
                if fallback:
                    print(f"      429 on free tier — switching {active_model} → {fallback}")
                    active_model = fallback
                    paid_cfg = MODEL_CONFIG.get(fallback, DEFAULT_MODEL_CONFIG)
                    rate_limiter = RateLimiter(paid_cfg["rpm"])
                    model_delay_state["fallback_model"] = fallback
                    model_delay_state["rate_limiter"] = rate_limiter
                    continue

                if _is_daily_cap_error(err_str):
                    raise  # true daily cap with no fallback — let caller handle

                wait = [5, 15, 45, 120][min(attempt, 3)]
                print(f"      429 rate limit — waiting {wait}s (attempt {attempt+1})")
                time.sleep(wait)
                continue

            last_was_rate_limit = False
            # Transient server errors
            if status in (500, 502, 503) or "timeout" in err_str or "server" in err_str:
                wait = [2, 8, 32][min(attempt, 2)]
                # Include the server's own message: a bare status code gives no way
                # to tell a context/template rejection from a real outage.
                print(f"      Transient error ({status or type(e).__name__}) — retry in {wait}s"
                      f"\n        detail: {str(e)[:300]}")
                time.sleep(wait)
                continue

            raise  # non-recoverable
    if last_was_rate_limit:
        raise RateLimitExhausted(f"All {MAX_TRANSIENT_RETRIES} retries exhausted (rate limited)")
    raise Exception(f"All {MAX_TRANSIENT_RETRIES} retries exhausted")


# ---------------------------------------------------------------------------
# Method runners
# ---------------------------------------------------------------------------
def run_zero_shot(client, model, system_prompt, input_json, mds, rate_limiter):
    tracker = TokenTracker()
    messages = build_messages("zero-shot", system_prompt, input_json)

    for attempt in range(1 + EMPTY_COMPLETION_RETRIES):
        resp = api_call_with_retry(client, mds, rate_limiter, model=model, messages=messages, temperature=0)
        tracker.add(resp)
        if not resp.choices or not resp.choices[0].message:
            raw = ""
        else:
            raw = get_response_text(resp.choices[0].message)
        if raw.strip():
            break
        if attempt < EMPTY_COMPLETION_RETRIES:
            print(f"      Empty completion (200 OK, 0 tokens) — retry {attempt + 1}/{EMPTY_COMPLETION_RETRIES}")

    messages.append({"role": "assistant", "content": raw[:500]})
    output = extract_json(raw)
    return output, 1, tracker, (messages if output is None else None)


def run_script(client, model, system_prompt, input_json, mds, max_retries, script_timeout, rate_limiter):
    tracker = TokenTracker()
    messages = build_messages("script", system_prompt, input_json)
    rounds = 0

    for attempt in range(1 + max_retries):
        resp = api_call_with_retry(client, mds, rate_limiter, model=model, messages=messages, temperature=0)
        tracker.add(resp)
        rounds += 1
        if not resp.choices or not resp.choices[0].message:
            return None, rounds, tracker, messages
        raw = get_response_text(resp.choices[0].message)
        # Append the response in full, exactly once per round. Truncating it to 500
        # chars left the model looking at a fragment of its own script cut off
        # mid-expression, right beside a "'{' was never closed" error it was asked
        # to fix — the stub was itself an instance of that error. The error and
        # timeout branches below used to append the full text a second time, so
        # every retry round also paid for the script twice in prompt tokens.
        messages.append({"role": "assistant", "content": raw})
        code = extract_code(raw)
        if not code:
            messages.append({"role": "user", "content": "Error: Could not find Python code in your response. Please provide the complete script."})
            continue

        sandbox = tempfile.mkdtemp()
        try:
            with open(os.path.join(sandbox, "input.json"), "w") as f:
                json.dump(input_json, f, indent=2)
            script_path = os.path.join(sandbox, "solve.py")
            with open(script_path, "w") as f:
                f.write(code)

            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True,
                timeout=script_timeout, cwd=sandbox,
            )
            if result.returncode == 0:
                output = extract_json(result.stdout)
                if output is not None:
                    return output, rounds, tracker, None
                # Exit code 0 but nothing parseable on stdout. The usual cause is a
                # script that defines its entrypoint and never calls it (no __main__
                # guard), so Python executes the definitions and exits cleanly having
                # printed nothing. This is trivially recoverable by saying so, but the
                # old code returned here and burned the case with every retry unused —
                # input_0287 scored 0/37 at rounds=1 after 1,802s for exactly this.
                if result.stdout.strip():
                    complaint = (
                        "Your script ran successfully but what it printed was not valid JSON. "
                        f"It printed:\n{result.stdout[:1000]}\n\n"
                        "Print ONLY the output JSON to stdout, nothing else."
                    )
                else:
                    complaint = (
                        "Your script ran successfully (exit code 0) but printed nothing to "
                        "stdout. Check that the script actually CALLS your function at top "
                        "level — defining it is not enough — and that it prints the result "
                        "with print(json.dumps(output))."
                    )
                messages.append({"role": "user", "content": complaint})
            else:
                err = result.stderr[:2000] if result.stderr else "Unknown error"
                messages.append({"role": "user", "content": f"Script error (exit code {result.returncode}):\n{err}\n\nPlease fix the script."})
        except subprocess.TimeoutExpired:
            messages.append({"role": "user", "content": f"Script timed out after {script_timeout}s. Please optimize."})
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    return None, rounds, tracker, messages


def run_tool_call(client, model, system_prompt, input_json, mds, max_rounds, rate_limiter):
    tracker = TokenTracker()
    messages = build_messages("tool-call", system_prompt, input_json)
    rounds = 0

    for _round in range(max_rounds):
        resp = api_call_with_retry(
            client, mds, rate_limiter,
            model=model, messages=messages,
            tools=[CALCULATE_TOOL], temperature=0,
        )
        tracker.add(resp)
        if not resp.choices or not resp.choices[0].message:
            return None, rounds + 1, tracker, messages
        choice = resp.choices[0]
        msg = choice.message

        if not msg.tool_calls:
            rounds += 1
            text = get_response_text(msg)
            messages.append({"role": "assistant", "content": text[:500]})
            output = extract_json(text)
            return output, rounds, tracker, (messages if output is None else None)

        messages.append(msg)
        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments)
                result = execute_calculate(args["operation"], args["operands"])
                tool_result = json.dumps(result)
            except Exception as e:
                tool_result = json.dumps({"error": str(e)})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": tool_result,
            })
        rounds += 1

    return None, rounds, tracker, messages


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def get_nested(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def safe_float(v):
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def pct_error(expected_val, actual_val):
    e = safe_float(expected_val)
    a = safe_float(actual_val)
    denom = max(abs(e), 1.0)
    return abs(e - a) / denom


def score_case(expected, actual):
    """Returns (scores, pct_errors) dicts keyed by field name."""
    scores = {}
    pct_errors = {}

    def leaf(name, *keys):
        ev = get_nested(expected, *keys)
        av = get_nested(actual, *keys) if actual else None
        if ev is None or av is None:
            scores[name] = 0
            pct_errors[name] = 1.0 if ev is not None else 0.0
            return
        try:
            ef, af = float(ev), float(av)
            correct = abs(ef - af) <= TOLERANCE
            scores[name] = 1 if correct else 0
            pct_errors[name] = 0.0 if correct else pct_error(ev, av)
        except (TypeError, ValueError):
            scores[name] = 0
            pct_errors[name] = 1.0

    # Salary
    for fname, keys in SALARY_FIELDS:
        leaf(fname, *keys)

    # Combined STCG
    if actual:
        exp_stcg = (safe_float(get_nested(expected, "Capital Gains", "STCG (Section 111A)"))
                    + safe_float(get_nested(expected, "Capital Gains", "STCG (Other)", "Total")))
        act_stcg = (safe_float(get_nested(actual, "Capital Gains", "STCG (Section 111A)"))
                    + safe_float(get_nested(actual, "Capital Gains", "STCG (Other)", "Total")))
        correct = abs(exp_stcg - act_stcg) <= TOLERANCE
        scores["combined_stcg"] = 1 if correct else 0
        pct_errors["combined_stcg"] = 0.0 if correct else abs(exp_stcg - act_stcg) / max(abs(exp_stcg), 1.0)
    else:
        scores["combined_stcg"] = 0
        pct_errors["combined_stcg"] = 1.0

    # Combined LTCG
    if actual:
        exp_ltcg = (safe_float(get_nested(expected, "Capital Gains", "LTCG (Section 112A)"))
                    + safe_float(get_nested(expected, "Capital Gains", "LTCG (Non-Equity)", "Total"))
                    + safe_float(get_nested(expected, "Capital Gains", "LTCG (Other)")))
        act_ltcg = (safe_float(get_nested(actual, "Capital Gains", "LTCG (Section 112A)"))
                    + safe_float(get_nested(actual, "Capital Gains", "LTCG (Non-Equity)", "Total"))
                    + safe_float(get_nested(actual, "Capital Gains", "LTCG (Other)")))
        correct = abs(exp_ltcg - act_ltcg) <= TOLERANCE
        scores["combined_ltcg"] = 1 if correct else 0
        pct_errors["combined_ltcg"] = 0.0 if correct else abs(exp_ltcg - act_ltcg) / max(abs(exp_ltcg), 1.0)
    else:
        scores["combined_ltcg"] = 0
        pct_errors["combined_ltcg"] = 1.0

    # Other sources
    for fname, keys in OTHER_SOURCES_FIELDS:
        leaf(fname, *keys)

    # Aggregates
    for fname, keys in AGGREGATE_FIELDS:
        leaf(fname, *keys)

    # Combined 80CCE
    if actual:
        exp_cce = (safe_float(get_nested(expected, "Deductions", "80C"))
                   + safe_float(get_nested(expected, "Deductions", "80CCC"))
                   + safe_float(get_nested(expected, "Deductions", "80CCD(1)")))
        act_cce = (safe_float(get_nested(actual, "Deductions", "80C"))
                   + safe_float(get_nested(actual, "Deductions", "80CCC"))
                   + safe_float(get_nested(actual, "Deductions", "80CCD(1)")))
        correct = abs(exp_cce - act_cce) <= TOLERANCE
        scores["80c_80ccc_80ccd1"] = 1 if correct else 0
        pct_errors["80c_80ccc_80ccd1"] = 0.0 if correct else abs(exp_cce - act_cce) / max(abs(exp_cce), 1.0)
    else:
        scores["80c_80ccc_80ccd1"] = 0
        pct_errors["80c_80ccc_80ccd1"] = 1.0

    # Deduction leaf fields
    for fname, keys in DEDUCTION_LEAF_FIELDS:
        leaf(fname, *keys)

    # Tax computation
    for fname, keys in TAX_FIELDS:
        leaf(fname, *keys)

    return scores, pct_errors


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------
def model_slug(model):
    return model.replace("/", "_").replace(":", "_")


def checkpoint_path(model, method):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    return CHECKPOINT_DIR / f"{model_slug(model)}__{method}.jsonl"


def load_checkpoint(model, method):
    """Returns (completed_set, results_list)."""
    path = checkpoint_path(model, method)
    completed = set()
    results = []
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            completed.add(entry["case_file"])
            results.append(entry)
    return completed, results


def save_checkpoint(model, method, result: CaseResult):
    path = checkpoint_path(model, method)
    entry = {  # noqa: thread-safe via _checkpoint_lock
        "case_file": result.case_file,
        "rounds_used": result.rounds_used,
        "parsed": result.parsed,
        "llm_output": result.llm_output,
        "scores": result.scores,
        "pct_errors": result.pct_errors,
        "total_score": result.total_score,
        "latency_sec": round(result.latency_sec, 2),
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "cost": round(result.cost, 6),
        "messages": _serialize_messages(result.messages),
    }
    with _checkpoint_lock:
        with open(path, "a") as f:
            f.write(json.dumps(entry) + "\n")


def _serialize_messages(messages):
    """Convert message objects to dicts for JSON serialization."""
    if messages is None:
        return None
    serialized = []
    for m in messages:
        if isinstance(m, dict):
            serialized.append(m)
        else:
            d = {"role": getattr(m, "role", "unknown")}
            if getattr(m, "content", None):
                d["content"] = m.content[:500]
            if getattr(m, "tool_calls", None):
                d["tool_calls"] = len(m.tool_calls)
            serialized.append(d)
    return serialized


# ---------------------------------------------------------------------------
# Case loading
# ---------------------------------------------------------------------------
def load_cases():
    case_files = sorted(glob.glob(str(GENERATED_DIR / "input_*.json")))
    if not case_files:
        print(f"ERROR: No test cases found in {GENERATED_DIR}")
        sys.exit(1)
    cases = []
    for f in case_files:
        with open(f) as fh:
            data = json.load(fh)
        cases.append({
            "file": os.path.basename(f),
            "input": data["input"],
            "expected": data["_expected"],
            "description": data.get("_description", ""),
            "archetype": data.get("_archetype") or "",
        })
    return cases


# ---------------------------------------------------------------------------
# Evaluate a single case
# ---------------------------------------------------------------------------
def evaluate_case(client, model, method, case, mds, args, rate_limiter):
    t0 = time.time()

    if method == "zero-shot":
        output, rounds, tracker, fail_msgs = run_zero_shot(
            client, model, args.system_prompt, case["input"], mds, rate_limiter
        )
    elif method == "script":
        output, rounds, tracker, fail_msgs = run_script(
            client, model, args.system_prompt, case["input"], mds,
            args.max_script_retries, args.script_timeout, rate_limiter
        )
    elif method == "tool-call":
        output, rounds, tracker, fail_msgs = run_tool_call(
            client, model, args.system_prompt, case["input"], mds,
            args.max_rounds, rate_limiter
        )

    latency = time.time() - t0
    parsed = output is not None
    scores, pct_errors = score_case(case["expected"], output)
    total = sum(scores.values())

    store_transcript = not parsed or total < 19

    return CaseResult(
        case_file=case["file"],
        description=case["description"],
        archetype=case["archetype"],
        model=model,
        method=method,
        rounds_used=rounds,
        parsed=parsed,
        llm_output=output,
        scores=scores,
        pct_errors=pct_errors,
        total_score=total,
        total_pct=round(total / 37, 4),
        latency_sec=latency,
        prompt_tokens=tracker.prompt_tokens,
        completion_tokens=tracker.completion_tokens,
        total_tokens=tracker.total_tokens,
        cost=tracker.cost,
        messages=fail_msgs if store_transcript else None,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def result_from_checkpoint_entry(entry, model, method, case_by_file=None):
    """Reconstruct enough of a CaseResult from a checkpoint dict for reporting."""
    case = (case_by_file or {}).get(entry["case_file"], {})
    return CaseResult(
        case_file=entry["case_file"],
        description=case.get("description", ""),
        archetype=case.get("archetype", ""),
        model=model,
        method=method,
        rounds_used=entry["rounds_used"],
        parsed=entry["parsed"],
        llm_output=None,
        scores=entry["scores"],
        pct_errors=entry.get("pct_errors", {}),
        total_score=entry["total_score"],
        total_pct=round(entry["total_score"] / 37, 4),
        latency_sec=entry.get("latency_sec", 0),
        prompt_tokens=entry.get("prompt_tokens", 0),
        completion_tokens=entry.get("completion_tokens", 0),
        total_tokens=entry.get("total_tokens", 0),
        cost=entry.get("cost", 0.0),
        messages=None,
    )


def write_per_model_method_csv(model, method, results):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fname = f"{model_slug(model)}__{method}_results.csv"
    path = RESULTS_DIR / fname

    fieldnames = (
        ["case_file", "description", "archetype", "model", "method", "rounds_used", "parsed",
         "latency_sec", "prompt_tokens", "completion_tokens", "total_tokens", "cost"]
        + ALL_FIELD_NAMES
        + [f"{f}_pct_error" for f in ALL_FIELD_NAMES]
        + ["total_score", "total_pct"]
    )

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            row = {
                "case_file": r.case_file,
                "description": r.description,
                "archetype": r.archetype,
                "model": r.model,
                "method": r.method,
                "rounds_used": r.rounds_used,
                "parsed": 1 if r.parsed else 0,
                "latency_sec": round(r.latency_sec, 2),
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "total_tokens": r.total_tokens,
                "cost": round(r.cost, 6),
                "total_score": r.total_score,
                "total_pct": r.total_pct,
            }
            for fname in ALL_FIELD_NAMES:
                row[fname] = r.scores.get(fname, 0)
                row[f"{fname}_pct_error"] = round(r.pct_errors.get(fname, 1.0), 4)
            writer.writerow(row)
    return path


def write_method_summary_csv(method, all_model_results):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{method}_summary.csv"

    fieldnames = [
        "model", "overall_accuracy",
        "salary_accuracy", "capital_gains_accuracy", "other_sources_accuracy",
        "aggregates_accuracy", "deductions_accuracy", "tax_computation_accuracy",
        "mean_rounds", "parse_fail_count", "total_cases",
        "mean_latency_sec", "mean_prompt_tokens", "mean_completion_tokens",
        "mean_total_tokens", "total_prompt_tokens", "total_completion_tokens",
        "total_cost", "mean_cost",
    ]

    # Merge into whatever is already on disk: a single-model run (--model X) must
    # not wipe out the rows for every other model previously evaluated.
    rows = {}
    if path.exists():
        with open(path, newline="") as f:
            for old in csv.DictReader(f):
                if old.get("model"):
                    rows[old["model"]] = {k: old.get(k, "") for k in fieldnames}

    for model, results in all_model_results.items():
        n = len(results)
        if n == 0:
            continue

        def section_acc(section_fields):
            total = sum(r.scores.get(f, 0) for r in results for f in section_fields)
            return round(total / (n * len(section_fields)), 4) if n else 0

        rows[model] = {
            "model": model,
            "overall_accuracy": round(sum(r.total_pct for r in results) / n, 4),
            "salary_accuracy": section_acc(SECTION_MAP["salary"]),
            "capital_gains_accuracy": section_acc(SECTION_MAP["capital_gains"]),
            "other_sources_accuracy": section_acc(SECTION_MAP["other_sources"]),
            "aggregates_accuracy": section_acc(SECTION_MAP["aggregates"]),
            "deductions_accuracy": section_acc(SECTION_MAP["deductions"]),
            "tax_computation_accuracy": section_acc(SECTION_MAP["tax_computation"]),
            "mean_rounds": round(sum(r.rounds_used for r in results) / n, 1),
            "parse_fail_count": sum(1 for r in results if not r.parsed),
            "total_cases": n,
            "mean_latency_sec": round(sum(r.latency_sec for r in results) / n, 2),
            "mean_prompt_tokens": round(sum(r.prompt_tokens for r in results) / n, 0),
            "mean_completion_tokens": round(sum(r.completion_tokens for r in results) / n, 0),
            "mean_total_tokens": round(sum(r.total_tokens for r in results) / n, 0),
            "total_prompt_tokens": sum(r.prompt_tokens for r in results),
            "total_completion_tokens": sum(r.completion_tokens for r in results),
            "total_cost": round(sum(r.cost for r in results), 6),
            "mean_cost": round(sum(r.cost for r in results) / n, 6),
        }

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for model in sorted(rows):
            writer.writerow(rows[model])
    return path


def write_cross_method_pivot():
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    methods = ["zero-shot", "script", "tool-call"]
    summaries = {}
    for m in methods:
        path = RESULTS_DIR / f"{m}_summary.csv"
        if path.exists():
            with open(path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    model = row["model"]
                    if model not in summaries:
                        summaries[model] = {}
                    summaries[model][m] = row

    if not summaries:
        return None

    path = RESULTS_DIR / "cross_method_summary.csv"
    fieldnames = ["model"]
    for m in methods:
        fieldnames.extend([f"{m}_accuracy", f"{m}_mean_tokens", f"{m}_mean_latency"])

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for model in sorted(summaries.keys()):
            row = {"model": model}
            for m in methods:
                if m in summaries[model]:
                    s = summaries[model][m]
                    row[f"{m}_accuracy"] = s.get("overall_accuracy", "")
                    row[f"{m}_mean_tokens"] = s.get("mean_total_tokens", "")
                    row[f"{m}_mean_latency"] = s.get("mean_latency_sec", "")
                else:
                    row[f"{m}_accuracy"] = ""
                    row[f"{m}_mean_tokens"] = ""
                    row[f"{m}_mean_latency"] = ""
            writer.writerow(row)
    return path


def print_console_summary(model, method, results):
    n = len(results)
    if n == 0:
        return
    overall = sum(r.total_pct for r in results) / n
    fail_count = sum(1 for r in results if not r.parsed)
    mean_rounds = sum(r.rounds_used for r in results) / n
    mean_latency = sum(r.latency_sec for r in results) / n
    mean_prompt = sum(r.prompt_tokens for r in results) / n
    mean_completion = sum(r.completion_tokens for r in results) / n
    mean_total = sum(r.total_tokens for r in results) / n
    total_tok = sum(r.total_tokens for r in results)
    total_cost = sum(r.cost for r in results)
    mean_cost = total_cost / n

    def section_acc(fields):
        t = sum(r.scores.get(f, 0) for r in results for f in fields)
        return t / (n * len(fields)) * 100

    print(f"\n=== Evaluation Report: {model} [{method}] ===")
    print(f"Overall accuracy:    {overall*100:.1f}% ({n} cases)")
    print(f"Failed to parse:     {fail_count} cases (scored as 0)")
    print(f"Mean rounds:         {mean_rounds:.1f} per case")
    print(f"\nPer-section accuracy:")
    print(f"  Salary (7 fields):            {section_acc(SECTION_MAP['salary']):.1f}%")
    print(f"  Capital Gains (2 fields):     {section_acc(SECTION_MAP['capital_gains']):.1f}%")
    print(f"  Other Sources (3 fields):     {section_acc(SECTION_MAP['other_sources']):.1f}%")
    print(f"  Aggregates (2 fields):        {section_acc(SECTION_MAP['aggregates']):.1f}%")
    print(f"  Deductions (9 fields):        {section_acc(SECTION_MAP['deductions']):.1f}%")
    print(f"  Tax Computation (14 fields):  {section_acc(SECTION_MAP['tax_computation']):.1f}%")
    print(f"\nCost / efficiency:")
    print(f"  Mean latency:          {mean_latency:.1f} sec/case")
    print(f"  Mean tokens:           {mean_total:,.0f} total ({mean_prompt:,.0f} prompt + {mean_completion:,.0f} completion)")
    print(f"  Total tokens (all):    {total_tok:,}")
    print(f"  Total cost:            ${total_cost:.4f} (${mean_cost:.4f}/case)")


# ---------------------------------------------------------------------------
# Per-model runner (called in parallel from main)
# ---------------------------------------------------------------------------
def _model_tag(model):
    """Short tag for log lines, e.g. 'gpt-oss-120b' from 'openai/gpt-oss-120b'."""
    return model.split("/")[-1]


def run_model(client, model, method, cases, args):
    """Run all cases for one model. Returns list[CaseResult]."""
    tag = _model_tag(model)
    cfg = MODEL_CONFIG.get(model, DEFAULT_MODEL_CONFIG)
    rate_limiter = RateLimiter(cfg["rpm"])
    concurrency = cfg["concurrency"]

    with _print_lock:
        print(f"\n[{tag}] Starting — rpm={cfg['rpm']}, concurrency={concurrency}")

    case_by_file = {c["file"]: c for c in cases}
    completed, checkpoint_entries = load_checkpoint(model, method)
    prior_results = [result_from_checkpoint_entry(e, model, method, case_by_file) for e in checkpoint_entries]

    pending_cases = [c for c in cases if c["file"] not in completed]
    if completed:
        with _print_lock:
            print(f"[{tag}] Resuming: {len(completed)} done, {len(pending_cases)} remaining")

    if not pending_cases:
        csv_path = write_per_model_method_csv(model, method, prior_results)
        with _print_lock:
            print_console_summary(model, method, prior_results)
            print(f"[{tag}] CSV: {csv_path}")
        return prior_results

    model_max_tokens = cfg.get("max_tokens", MAX_OUTPUT_TOKENS)
    model_delay_state = {"consecutive_429": 0, "delay": args.delay, "json_format_supported": False,
                         "max_tokens": model_max_tokens}
    new_results = []
    total_count = len(cases)
    completed_files = set(completed)

    def process_case(case):
        rl = model_delay_state.get("rate_limiter", rate_limiter)
        return evaluate_case(client, model, method, case, model_delay_state, args, rl)

    def _run_batch(batch_cases):
        """Run cases with incremental submission.

        Feeds new cases as old ones complete (sliding window of *concurrency*).
        On RateLimitExhausted: stop feeding new cases, let in-flight drain.
        If any in-flight succeeds, reset the flag and resume feeding.
        Returns (results, rate_limit_halted, skipped_cases).
        """
        case_iter = iter(batch_cases)
        batch_results = []
        skipped_cases = []
        consecutive_skips = 0
        rate_limit_paused = False
        stop = False

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_case = {}

            # seed the initial window
            for case in itertools.islice(case_iter, concurrency):
                future_to_case[executor.submit(process_case, case)] = case

            while future_to_case:
                done_futures = {f for f in future_to_case if f.done()}
                if not done_futures:
                    time.sleep(0.1)
                    continue

                for future in done_futures:
                    case = future_to_case.pop(future)
                    count = len(completed_files) + len(batch_results) + 1

                    try:
                        result = future.result()
                        save_checkpoint(model, method, result)
                        batch_results.append(result)
                        consecutive_skips = 0

                        if rate_limit_paused:
                            with _print_lock:
                                print(f"[{tag}] In-flight request succeeded — resuming submission")
                            rate_limit_paused = False

                        status = "OK" if result.parsed else "PARSE_FAIL"
                        with _print_lock:
                            print(f"[{tag}] [{count}/{total_count}] {case['file']} "
                                  f"{status} score={result.total_score}/37 "
                                  f"({result.total_pct*100:.0f}%) "
                                  f"rounds={result.rounds_used} "
                                  f"latency={result.latency_sec:.1f}s "
                                  f"tokens={result.total_tokens} "
                                  f"cost=${result.cost:.4f}")

                        _cost_guard.case_completed()

                    except RuntimeError as e:
                        if "BUDGET" in str(e):
                            with _print_lock:
                                print(f"\n[{tag}] COST GUARD: {e}")
                                print("ABORTING — budget exceeded.")
                            os._exit(1)
                        raise

                    except RateLimitExhausted:
                        consecutive_skips += 1
                        skipped_cases.append(case)
                        with _print_lock:
                            print(f"[{tag}] [{count}/{total_count}] {case['file']} "
                                  f"SKIP (rate limited)")
                        if not rate_limit_paused:
                            rate_limit_paused = True
                            with _print_lock:
                                print(f"[{tag}] Rate limited — pausing new submissions, "
                                      f"draining {len(future_to_case)} in-flight request(s)")

                    except Exception as e:
                        err_str = str(e).lower()
                        with _print_lock:
                            print(f"[{tag}] [{count}/{total_count}] {case['file']} "
                                  f"SKIP ({type(e).__name__}: {str(e)[:80]})")

                        if _is_daily_cap_error(err_str):
                            stop = True
                            break

                        consecutive_skips += 1
                        if consecutive_skips >= CONSECUTIVE_SKIP_LIMIT:
                            with _print_lock:
                                print(f"[{tag}] {CONSECUTIVE_SKIP_LIMIT} consecutive "
                                      f"failures — stopping model")
                            stop = True
                            break

                if stop:
                    break

                # feed new cases if not paused
                if not rate_limit_paused and not stop:
                    while len(future_to_case) < concurrency:
                        nxt = next(case_iter, None)
                        if nxt is None:
                            break
                        future_to_case[executor.submit(process_case, nxt)] = nxt

        # any un-submitted cases go into skipped
        skipped_cases.extend(case_iter)
        rate_limit_halted = rate_limit_paused  # still paused when batch ended
        return batch_results, rate_limit_halted, skipped_cases

    cooldowns_used = 0
    remaining_cases = pending_cases

    while remaining_cases:
        batch_results, rate_limit_halted, remaining_cases = _run_batch(remaining_cases)
        new_results.extend(batch_results)
        completed_files.update(r.case_file for r in batch_results)

        if not rate_limit_halted or not remaining_cases:
            break

        if cooldowns_used >= FREE_COOLDOWN_MAX_RETRIES:
            with _print_lock:
                print(f"[{tag}] Rate-limited again after {cooldowns_used} cooldown(s) — halting model")
            break

        cooldowns_used += 1
        model_delay_state["consecutive_429"] = 0
        with _print_lock:
            print(f"[{tag}] Cooling down for {FREE_COOLDOWN_SECS}s before retry "
                  f"({cooldowns_used}/{FREE_COOLDOWN_MAX_RETRIES}) ...")
        time.sleep(FREE_COOLDOWN_SECS)

    results = prior_results + new_results
    csv_path = write_per_model_method_csv(model, method, results)
    with _print_lock:
        print_console_summary(model, method, results)
        print(f"[{tag}] CSV: {csv_path}")
    return results


# ---------------------------------------------------------------------------
# Log tee — writes stdout to both console and a timestamped log file
# ---------------------------------------------------------------------------
class _Tee:
    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for s in self._streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self._streams:
            s.flush()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="LLM benchmark evaluator for Indian tax calculator")
    parser.add_argument("--method", choices=["zero-shot", "script", "tool-call"], default="zero-shot")
    parser.add_argument("--model", type=str, default=None, help="OpenRouter model ID; if omitted runs all models")
    parser.add_argument("--max-rounds", type=int, default=MAX_TOOL_ROUNDS)
    parser.add_argument("--max-script-retries", type=int, default=MAX_SCRIPT_RETRIES)
    parser.add_argument("--script-timeout", type=int, default=SCRIPT_TIMEOUT)
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN_CASES)
    parser.add_argument("--max-cases", type=int, default=MAX_CASES, help="Max number of cases to evaluate (default 500)")
    parser.add_argument("--budget", type=float, default=DEFAULT_BUDGET, help="Max USD to spend before halting (default $17)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for case selection (default 42)")
    args = parser.parse_args()

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    log_path = LOGS_DIR / f"run_{args.method}_{ts}.log"
    log_file = open(log_path, "w")
    sys.stdout = _Tee(sys.__stdout__, log_file)
    sys.stderr = _Tee(sys.__stderr__, log_file)

    args.system_prompt = load_system_prompt()
    client = get_client(args.model)
    all_cases = load_cases()
    random.Random(args.seed).shuffle(all_cases)
    cases = all_cases[:args.max_cases]
    models = [args.model] if args.model else MODELS

    global _cost_guard
    _cost_guard = CostGuard(budget=args.budget)

    print(f"Method: {args.method} | Models: {len(models)} | Cases: {len(cases)} (seed={args.seed})")
    print(f"Constants: max_rounds={args.max_rounds}, max_script_retries={args.max_script_retries}, "
          f"script_timeout={args.script_timeout}s, max_cases={args.max_cases}, budget=${args.budget:.2f}")
    for m in models:
        cfg = MODEL_CONFIG.get(m, DEFAULT_MODEL_CONFIG)
        print(f"  {_model_tag(m):35s} rpm={cfg['rpm']:2d}  concurrency={cfg['concurrency']}")

    # Local models cannot cost anything, so skip the credits polling entirely
    # rather than hit OpenRouter every COST_CHECK_INTERVAL cases to be told $0.
    if not all(is_local_model(m) for m in models):
        _cost_guard.initialize()

    if len(models) == 1:
        results = run_model(client, models[0], args.method, cases, args)
        all_model_results = {models[0]: results}
    else:
        all_model_results = {}
        with ThreadPoolExecutor(max_workers=len(models)) as model_executor:
            future_to_model = {
                model_executor.submit(run_model, client, m, args.method, cases, args): m
                for m in models
            }
            for future in as_completed(future_to_model):
                m = future_to_model[future]
                try:
                    all_model_results[m] = future.result()
                except Exception as e:
                    with _print_lock:
                        print(f"[{_model_tag(m)}] MODEL FAILED: {e}")
                    all_model_results[m] = []

    # Write method-level summary
    summary_path = write_method_summary_csv(args.method, all_model_results)
    print(f"\nMethod summary: {summary_path}")

    # Attempt cross-method pivot
    pivot_path = write_cross_method_pivot()
    if pivot_path:
        print(f"Cross-method pivot: {pivot_path}")

    total_spent = _cost_guard.spent()
    if total_spent is not None:
        print(f"Total spent: ${total_spent:.4f}")

    print(f"\nLog saved: {log_path}")
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    log_file.close()


if __name__ == "__main__":
    main()
