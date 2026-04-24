#!/usr/bin/env python3
"""Interactive prompt tuning tool for the LLM tax benchmark.

Runs a small sample of test cases against one model from each tier (weak, mid,
strong) and reports JSON parse success, key-name mismatches, and field-by-field
scores.  The user edits tests/prompts/system_prompt.txt between runs and
re-executes until all tiers reliably produce parseable JSON.

Usage:
    python3 tests/tune_prompt.py                          # default: zero-shot, 5 cases
    python3 tests/tune_prompt.py --method script --cases 5
    python3 tests/tune_prompt.py --method tool-call --cases 5
"""

import argparse
import glob
import hashlib
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
TUNING_LOG = SCRIPT_DIR / "prompts" / "tuning_log.jsonl"

# ---------------------------------------------------------------------------
# Tuning models — one per tier
# ---------------------------------------------------------------------------
TUNING_MODELS = {
    # 503 retry: 7 remaining cases for both paid OpenAI models
    "strong_1": "openai/gpt-oss-120b",
    "weak_2":   "openai/gpt-oss-20b",
}

# ---------------------------------------------------------------------------
# Constants (mirror evaluate_llm.py)
# ---------------------------------------------------------------------------
MAX_TOOL_ROUNDS = 20
MAX_SCRIPT_RETRIES = 3
SCRIPT_TIMEOUT = 20
TOLERANCE = 0.01
DELAY_BETWEEN_CALLS = 3.0

# ---------------------------------------------------------------------------
# Expected output schema keys (for key-name checking)
# ---------------------------------------------------------------------------
EXPECTED_SCHEMA = {
    "Under Head Salaries": {
        "Gross Salary": 0,
        "Exemptions": {"Section 10(13A)": 0, "Section 10(5)": 0},
        "Section 16(ia)": 0, "Section 16(ii)": 0, "Section 16(iii)": 0,
        "Net Salary": 0,
    },
    "Capital Gains": {
        "STCG (Section 111A)": 0,
        "STCG (Other)": {"Bonds": 0, "Debentures": 0, "G-Secs": 0, "Mutual Funds": 0, "Total": 0},
        "LTCG (Section 112A)": 0,
        "LTCG (Non-Equity)": {"Bonds": 0, "Debentures": 0, "G-Secs": 0, "Mutual Funds": 0, "Total": 0},
        "LTCG (Other)": 0,
    },
    "Income from Other Sources": {
        "Savings Bank Interest": 0, "Deposit Interest": 0,
        "Other Interest": {"EPF Taxable Interest": 0},
    },
    "Gross Total Income": 0,
    "Deductions": {
        "80C": 0, "80CCC": 0, "80CCD(1)": 0, "80CCD(1B)": 0, "80CCD(2)": 0,
        "80D": 0, "80E": 0, "80G": 0, "80TTA": 0, "80TTB": 0,
        "Total Deductions": 0,
    },
    "Total Taxable Income": 0,
    "Tax Computation": {
        "Tax at Slab Rates": 0,
        "Tax on STCG (Section 111A)": 0, "Tax on STCG (Other)": 0,
        "Tax on LTCG (Section 112A)": 0, "Tax on LTCG (Non-Equity)": 0,
        "Tax on LTCG (Other)": 0,
        "Total Tax Before Rebate": 0,
        "Less: Rebate under Section 87A": 0, "Tax After Rebate": 0,
        "Surcharge": 0, "Health and Education Cess": 0,
        "Total Tax Liability": 0, "Less: TDS": 0,
        "Net Tax Payable / Refund": 0,
    },
}

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
# OpenRouter client
# ---------------------------------------------------------------------------
def get_client():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: Set OPENROUTER_API_KEY environment variable.")
        sys.exit(1)
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


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
        user_content += (
            "\n\nUse the calculate tool for ALL arithmetic — never perform mental "
            "math. You may request multiple calculate calls in parallel when "
            "calculations are independent."
        )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# JSON extraction
# ---------------------------------------------------------------------------
def _clean_json_text(text):
    """Strip control characters that some models embed in JSON output."""
    return re.sub(r"[\x00-\x09\x0b\x0c\x0e-\x1f]", "", text)


def _valid_output(obj):
    """Return obj if it's a non-empty dict, else None."""
    return obj if isinstance(obj, dict) and len(obj) > 0 else None


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


def _normalize_keys(obj):
    """Recursively fix tokenizer-mangled key names.

    Matches keys by stripping spaces and comparing case-insensitively
    against the expected schema. "Under HeadSalaries" → "Under Head Salaries".
    """
    if not isinstance(obj, dict):
        return obj
    normalized = {}
    for k, v in obj.items():
        stripped = k.replace(" ", "").lower()
        correct_key = _KEY_LOOKUP.get(stripped, k)
        normalized[correct_key] = _normalize_keys(v)
    return normalized


def extract_json(text):
    """Extract the largest valid non-empty JSON object from text.

    Skips empty {} and trivially small fragments that appear in reasoning
    preamble. Prefers the largest valid JSON object found.
    """
    # Try the raw text first
    try:
        result = _valid_output(json.loads(text))
        if result is not None:
            return _normalize_keys(result)
    except (json.JSONDecodeError, TypeError):
        pass
    if not text:
        return None
    # Try after cleaning control characters
    cleaned = _clean_json_text(text)
    try:
        result = _valid_output(json.loads(cleaned))
        if result is not None:
            return _normalize_keys(result)
    except (json.JSONDecodeError, TypeError):
        pass
    # Try stripping markdown fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", cleaned, re.DOTALL)
    if fenced:
        try:
            result = _valid_output(json.loads(fenced.group(1)))
            if result is not None:
                return _normalize_keys(result)
        except json.JSONDecodeError:
            pass
    # Find the largest valid non-empty JSON object via brace matching
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
    """Extract Python code from a response (code block or raw)."""
    fenced = re.search(r"```(?:python)?\s*\n(.*?)\n\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    lines = text.strip().split("\n")
    code_lines = [l for l in lines if not l.startswith("#") or l.startswith("#!/")]
    if any("import" in l or "print" in l or "open(" in l for l in code_lines):
        return text.strip()
    return None


# ---------------------------------------------------------------------------
# Response text extraction — handles reasoning models
# ---------------------------------------------------------------------------
def get_response_text(message):
    """Extract usable text from a chat message.

    Some models (e.g. Nemotron) put output in a `reasoning` field instead of
    `content`. We check both, preferring `content` when present.
    """
    text = message.content or ""
    if not text:
        reasoning = getattr(message, "reasoning", None) or ""
        if reasoning:
            text = reasoning
    return text


# ---------------------------------------------------------------------------
# Cost guard
# ---------------------------------------------------------------------------
TUNING_BUDGET = 5.00  # USD — max spend for tuning runs


class CostGuard:
    """Tracks cumulative and per-model cost. Halts if budget exceeded."""

    def __init__(self, budget=TUNING_BUDGET):
        self.budget = budget
        self.cumulative_cost = 0.0
        self.per_model_cost = {}  # model -> float
        self._lock = threading.Lock()

    def check(self, response, model=None):
        usage = getattr(response, "usage", None)
        if usage is None:
            return 0.0
        cost = getattr(usage, "cost", None)
        if cost is None and isinstance(usage, dict):
            cost = usage.get("cost")
        call_cost = float(cost) if cost is not None else 0.0
        if call_cost > 0:
            with self._lock:
                self.cumulative_cost += call_cost
                if model:
                    self.per_model_cost[model] = self.per_model_cost.get(model, 0.0) + call_cost
                if self.cumulative_cost > self.budget:
                    raise RuntimeError(
                        f"BUDGET EXCEEDED: ${self.cumulative_cost:.4f} spent "
                        f"(budget: ${self.budget:.2f}). Halting."
                    )
        return call_cost


# ---------------------------------------------------------------------------
# Method runners
# ---------------------------------------------------------------------------
_cost_guard = CostGuard()

# Per-model tracking of whether response_format=json_object is supported
_json_format_support = {}  # model -> bool


MAX_OUTPUT_TOKENS = 16384


def _create_completion(client, model, *, tools=None, **kwargs):
    """Wrapper with response_format=json_object fallback + 429 retry."""
    use_json = _json_format_support.get(model, False)
    call_kwargs = dict(kwargs, model=model)
    call_kwargs.setdefault("max_tokens", MAX_OUTPUT_TOKENS)
    if tools:
        call_kwargs["tools"] = tools
    if use_json and tools is None:
        call_kwargs["response_format"] = {"type": "json_object"}

    for attempt in range(2):
        try:
            resp = client.chat.completions.create(**call_kwargs)
            _cost_guard.check(resp, model=model)

            # Check for empty choices (some models return empty when
            # response_format is unsupported but don't raise an error)
            if not resp.choices or resp.choices[0].message is None:
                if use_json:
                    _json_format_support[model] = False
                    use_json = False
                    if "response_format" in call_kwargs:
                        del call_kwargs["response_format"]
                    continue
                raise Exception(f"Empty response from {model}")

            return resp
        except Exception as e:
            err_str = str(e).lower()
            status = getattr(e, "status_code", None) or getattr(e, "code", None)

            # response_format not supported — disable and retry immediately
            if use_json and ("response_format" in err_str
                             or "json_object" in err_str
                             or "json mode" in err_str
                             or "unsupported" in err_str
                             or "not supported" in err_str
                             or "none" in err_str):
                _json_format_support[model] = False
                use_json = False
                if "response_format" in call_kwargs:
                    del call_kwargs["response_format"]
                continue

            # 429 rate limit — wait and retry
            if status == 429 or "429" in err_str or "rate" in err_str:
                wait = [15, 60][min(attempt, 1)]
                print(f"      429 rate limit — waiting {wait}s (attempt {attempt+1}/2)")
                time.sleep(wait)
                continue

            raise
    raise Exception(f"All retries exhausted for {model}")


def run_zero_shot(client, model, system_prompt, input_json):
    messages = build_messages("zero-shot", system_prompt, input_json)
    resp = _create_completion(client, model, messages=messages, temperature=0)
    msg = resp.choices[0].message
    raw = get_response_text(msg)
    if not raw:
        return None, "(empty response)"
    return extract_json(raw), raw


def run_script(client, model, system_prompt, input_json):
    messages = build_messages("script", system_prompt, input_json)
    raw_responses = []

    for attempt in range(1 + MAX_SCRIPT_RETRIES):
        resp = _create_completion(client, model, messages=messages, temperature=0)
        if not resp.choices or not resp.choices[0].message:
            return None, "(empty response from model)"
        raw = get_response_text(resp.choices[0].message)
        raw_responses.append(raw)
        code = extract_code(raw)
        if not code:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": "Error: Could not find Python code in your response. Please provide the complete script."})
            continue

        sandbox = tempfile.mkdtemp()
        try:
            input_path = os.path.join(sandbox, "input.json")
            script_path = os.path.join(sandbox, "solve.py")
            with open(input_path, "w") as f:
                json.dump(input_json, f, indent=2)
            with open(script_path, "w") as f:
                f.write(code)

            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True, text=True,
                timeout=SCRIPT_TIMEOUT, cwd=sandbox,
            )
            if result.returncode == 0:
                parsed = extract_json(result.stdout)
                return parsed, "\n---ATTEMPT---\n".join(raw_responses)
            else:
                error_msg = result.stderr[:2000] if result.stderr else "Unknown error"
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"Script error (exit code {result.returncode}):\n{error_msg}\n\nPlease fix the script and provide the complete corrected version."})
        except subprocess.TimeoutExpired:
            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Script timed out after {SCRIPT_TIMEOUT} seconds. Please optimize and provide the complete corrected version."})
        finally:
            shutil.rmtree(sandbox, ignore_errors=True)

    return None, "\n---ATTEMPT---\n".join(raw_responses)


def run_tool_call(client, model, system_prompt, input_json):
    messages = build_messages("tool-call", system_prompt, input_json)
    all_raw = []

    for _round in range(MAX_TOOL_ROUNDS):
        resp = _create_completion(
            client, model, messages=messages,
            tools=[CALCULATE_TOOL], temperature=0,
        )
        if not resp.choices or not resp.choices[0].message:
            return None, "\n".join(all_raw) if all_raw else "(empty response from model)"
        choice = resp.choices[0]
        msg = choice.message

        text = get_response_text(msg)
        if text:
            all_raw.append(text)

        if not msg.tool_calls:
            parsed = extract_json(text)
            return parsed, "\n".join(all_raw)

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

    return None, "\n".join(all_raw)


# ---------------------------------------------------------------------------
# Key checking
# ---------------------------------------------------------------------------
def collect_keys(d, prefix=""):
    """Collect all dot-separated key paths from a nested dict."""
    keys = set()
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        keys.add(path)
        if isinstance(v, dict):
            keys.update(collect_keys(v, path))
    return keys


def check_keys(output):
    """Compare output keys against expected schema. Returns (missing, extra)."""
    expected_keys = collect_keys(EXPECTED_SCHEMA)
    actual_keys = collect_keys(output) if isinstance(output, dict) else set()
    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys
    return sorted(missing), sorted(extra)


# ---------------------------------------------------------------------------
# Scoring (simplified for tuning — same logic as evaluate_llm.py)
# ---------------------------------------------------------------------------
def get_nested(d, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def score_field(expected_val, actual_val):
    if expected_val is None or actual_val is None:
        return 0
    try:
        return 1 if abs(float(expected_val) - float(actual_val)) <= TOLERANCE else 0
    except (TypeError, ValueError):
        return 0


def score_case(expected, actual):
    """Score a single case. Returns (scores_dict, total, max_possible)."""
    if actual is None:
        return {}, 0, 37

    scores = {}

    def leaf(name, *keys):
        scores[name] = score_field(get_nested(expected, *keys), get_nested(actual, *keys))

    leaf("Gross Salary", "Under Head Salaries", "Gross Salary")
    leaf("Section 10(13A)", "Under Head Salaries", "Exemptions", "Section 10(13A)")
    leaf("Section 10(5)", "Under Head Salaries", "Exemptions", "Section 10(5)")
    leaf("Section 16(ia)", "Under Head Salaries", "Section 16(ia)")
    leaf("Section 16(ii)", "Under Head Salaries", "Section 16(ii)")
    leaf("Section 16(iii)", "Under Head Salaries", "Section 16(iii)")
    leaf("Net Salary", "Under Head Salaries", "Net Salary")

    # Combined STCG
    def safe_float(v):
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    exp_stcg = (safe_float(get_nested(expected, "Capital Gains", "STCG (Section 111A)"))
                + safe_float(get_nested(expected, "Capital Gains", "STCG (Other)", "Total")))
    act_stcg = (safe_float(get_nested(actual, "Capital Gains", "STCG (Section 111A)"))
                + safe_float(get_nested(actual, "Capital Gains", "STCG (Other)", "Total")))
    scores["Combined STCG"] = 1 if abs(exp_stcg - act_stcg) <= TOLERANCE else 0

    exp_ltcg = (safe_float(get_nested(expected, "Capital Gains", "LTCG (Section 112A)"))
                + safe_float(get_nested(expected, "Capital Gains", "LTCG (Non-Equity)", "Total"))
                + safe_float(get_nested(expected, "Capital Gains", "LTCG (Other)")))
    act_ltcg = (safe_float(get_nested(actual, "Capital Gains", "LTCG (Section 112A)"))
                + safe_float(get_nested(actual, "Capital Gains", "LTCG (Non-Equity)", "Total"))
                + safe_float(get_nested(actual, "Capital Gains", "LTCG (Other)")))
    scores["Combined LTCG"] = 1 if abs(exp_ltcg - act_ltcg) <= TOLERANCE else 0

    leaf("Savings Bank Interest", "Income from Other Sources", "Savings Bank Interest")
    leaf("Deposit Interest", "Income from Other Sources", "Deposit Interest")
    leaf("EPF Taxable Interest", "Income from Other Sources", "Other Interest", "EPF Taxable Interest")

    leaf("Gross Total Income", "Gross Total Income")
    leaf("Total Taxable Income", "Total Taxable Income")

    # Combined 80CCE
    exp_80cce = (safe_float(get_nested(expected, "Deductions", "80C"))
                 + safe_float(get_nested(expected, "Deductions", "80CCC"))
                 + safe_float(get_nested(expected, "Deductions", "80CCD(1)")))
    act_80cce = (safe_float(get_nested(actual, "Deductions", "80C"))
                 + safe_float(get_nested(actual, "Deductions", "80CCC"))
                 + safe_float(get_nested(actual, "Deductions", "80CCD(1)")))
    scores["80C+80CCC+80CCD(1)"] = 1 if abs(exp_80cce - act_80cce) <= TOLERANCE else 0

    leaf("80CCD(1B)", "Deductions", "80CCD(1B)")
    leaf("80CCD(2)", "Deductions", "80CCD(2)")
    leaf("80D", "Deductions", "80D")
    leaf("80E", "Deductions", "80E")
    leaf("80G", "Deductions", "80G")
    leaf("80TTA", "Deductions", "80TTA")
    leaf("80TTB", "Deductions", "80TTB")
    leaf("Total Deductions", "Deductions", "Total Deductions")

    leaf("Tax at Slab Rates", "Tax Computation", "Tax at Slab Rates")
    leaf("Tax on STCG (Section 111A)", "Tax Computation", "Tax on STCG (Section 111A)")
    leaf("Tax on STCG (Other)", "Tax Computation", "Tax on STCG (Other)")
    leaf("Tax on LTCG (Section 112A)", "Tax Computation", "Tax on LTCG (Section 112A)")
    leaf("Tax on LTCG (Non-Equity)", "Tax Computation", "Tax on LTCG (Non-Equity)")
    leaf("Tax on LTCG (Other)", "Tax Computation", "Tax on LTCG (Other)")
    leaf("Total Tax Before Rebate", "Tax Computation", "Total Tax Before Rebate")
    leaf("Less: Rebate under Section 87A", "Tax Computation", "Less: Rebate under Section 87A")
    leaf("Tax After Rebate", "Tax Computation", "Tax After Rebate")
    leaf("Surcharge", "Tax Computation", "Surcharge")
    leaf("Health and Education Cess", "Tax Computation", "Health and Education Cess")
    leaf("Total Tax Liability", "Tax Computation", "Total Tax Liability")
    leaf("Less: TDS", "Tax Computation", "Less: TDS")
    leaf("Net Tax Payable / Refund", "Tax Computation", "Net Tax Payable / Refund")

    total = sum(scores.values())
    return scores, total, 37


# ---------------------------------------------------------------------------
# Failure pattern detection
# ---------------------------------------------------------------------------
def detect_failure_patterns(raw_text):
    patterns = []
    if "```" in raw_text:
        patterns.append("markdown_fences")
    stripped = raw_text.strip()
    if stripped and not stripped.startswith("{"):
        patterns.append("preamble_text")
    if re.search(r"\d+e[+-]?\d+", raw_text, re.IGNORECASE):
        patterns.append("scientific_notation")
    return patterns


# ---------------------------------------------------------------------------
# Rate limiter (thread-safe)
# ---------------------------------------------------------------------------
TUNE_RPM = 18
TUNE_CONCURRENCY = 9


class RateLimiter:
    def __init__(self, rpm):
        self._interval = 60.0 / rpm
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self):
        with self._lock:
            now = time.monotonic()
            gap = self._interval - (now - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.monotonic()


_tune_rate_limiter = RateLimiter(TUNE_RPM)


# ---------------------------------------------------------------------------
# Single task: run one (model, case) pair
# ---------------------------------------------------------------------------
def _run_one(client, model, method, system_prompt, case):
    """Run a single case for a model. Returns (tier, model, case_file, output, raw, error)."""
    _tune_rate_limiter.wait()
    try:
        if method == "zero-shot":
            output, raw = run_zero_shot(client, model, system_prompt, case["input"])
        elif method == "script":
            output, raw = run_script(client, model, system_prompt, case["input"])
        elif method == "tool-call":
            output, raw = run_tool_call(client, model, system_prompt, case["input"])
        return model, case["file"], output, raw, None
    except Exception as e:
        return model, case["file"], None, "", e


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Interactive prompt tuning for LLM tax benchmark")
    parser.add_argument("--method", choices=["zero-shot", "script", "tool-call"], default="zero-shot")
    parser.add_argument("--cases", type=int, default=3)
    parser.add_argument("--seed", type=int, default=None, help="Random seed for case selection")
    parser.add_argument("--case-files", nargs="+", default=None, help="Specific case filenames (e.g. input_0418.json)")
    parser.add_argument("--concurrency", type=int, default=TUNE_CONCURRENCY)
    parser.add_argument("--rpm", type=int, default=TUNE_RPM)
    args = parser.parse_args()

    global _tune_rate_limiter
    _tune_rate_limiter = RateLimiter(args.rpm)

    client = get_client()
    system_prompt = load_system_prompt()
    prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:8]

    if args.case_files:
        selected = [str(GENERATED_DIR / f) for f in args.case_files]
    else:
        case_files = sorted(glob.glob(str(GENERATED_DIR / "input_*.json")))
        if not case_files:
            print(f"ERROR: No test cases found in {GENERATED_DIR}")
            sys.exit(1)
        rng = random.Random(args.seed)
        selected = rng.sample(case_files, min(args.cases, len(case_files)))

    cases = []
    for f in selected:
        with open(f) as fh:
            data = json.load(fh)
        cases.append({
            "file": os.path.basename(f),
            "input": data["input"],
            "expected": data["_expected"],
            "description": data.get("_description", ""),
        })

    print(f"\n{'='*70}")
    print(f"Prompt Tuning Run")
    print(f"  Method:      {args.method}")
    print(f"  Cases:       {len(cases)}")
    print(f"  Models:      {len(TUNING_MODELS)}")
    print(f"  Concurrency: {args.concurrency} | RPM: {args.rpm}")
    print(f"  Prompt hash: {prompt_hash}")
    print(f"{'='*70}\n")

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "method": args.method,
        "prompt_hash": prompt_hash,
        "cases_tested": len(cases),
        "case_files": [c["file"] for c in cases],
        "results": {},
        "change_description": "",
    }

    # Build all (model, case) tasks
    tasks = []
    for tier, model in TUNING_MODELS.items():
        for case in cases:
            tasks.append((tier, model, case))

    # Per-model accumulators
    model_data = {}
    for tier, model in TUNING_MODELS.items():
        model_data[model] = {
            "tier": tier,
            "parse_ok": 0,
            "total_score": 0,
            "all_failures": [],
            "all_key_issues": [],
        }

    print_lock = threading.Lock()
    aborted = False

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        future_map = {}
        for tier, model, case in tasks:
            fut = executor.submit(_run_one, client, model, args.method, system_prompt, case)
            future_map[fut] = (tier, model, case)

        for fut in as_completed(future_map):
            if aborted:
                break

            tier, model, case = future_map[fut]
            ret_model, case_file, output, raw, error = fut.result()
            md = model_data[model]

            with print_lock:
                print(f"  [{md['tier'].upper()}] {model} | {case_file}")

                if error is not None:
                    if isinstance(error, RuntimeError) and "BUDGET" in str(error):
                        print(f"    COST GUARD: {error}")
                        print("    ABORTING — budget exceeded.")
                        aborted = True
                        break
                    print(f"    API ERROR: {error}")
                    md["all_failures"].append("api_error")
                elif output is not None:
                    md["parse_ok"] += 1
                    missing, extra = check_keys(output)
                    scores, sc_total, sc_max = score_case(case["expected"], output)
                    md["total_score"] += sc_total
                    print(f"    Parse: OK | Score: {sc_total}/{sc_max} ({sc_total/sc_max*100:.1f}%)")
                    if missing:
                        print(f"    Missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}")
                        md["all_key_issues"].extend(missing)
                    if extra:
                        print(f"    Extra keys:   {extra[:5]}{'...' if len(extra) > 5 else ''}")
                else:
                    print(f"    Parse: FAIL")
                    pats = detect_failure_patterns(raw)
                    if pats:
                        print(f"    Patterns: {pats}")
                    md["all_failures"].extend(pats if pats else ["unknown"])
                    print(f"    Raw preview: {raw[:200].replace(chr(10), '\\n')}")

    if aborted:
        print(f"\n{'='*70}")
        print("RUN ABORTED — budget exceeded.")
        print(f"{'='*70}")
        sys.exit(1)

    # Print summaries
    n = len(cases)
    for model, md in model_data.items():
        mean_score = md["total_score"] / max(md["parse_ok"], 1)
        model_cost = _cost_guard.per_model_cost.get(model, 0.0)
        print(f"\n  --- {md['tier'].upper()} SUMMARY ({model}) ---")
        print(f"  Parse rate:  {md['parse_ok']}/{n} ({md['parse_ok']/n*100:.0f}%)")
        print(f"  Mean score (parsed): {mean_score:.1f}/37 ({mean_score/37*100:.1f}%)")
        print(f"  Cost: ${model_cost:.4f}")
        if md["all_failures"]:
            counts = Counter(md["all_failures"])
            print(f"  Failure patterns: {dict(counts)}")
        if md["all_key_issues"]:
            top = Counter(md["all_key_issues"]).most_common(5)
            print(f"  Top missing keys: {top}")

        log_entry["results"][model] = {
            "tier": md["tier"],
            "parse_rate": md["parse_ok"] / n,
            "mean_score_parsed": round(mean_score / 37, 4),
            "cost": round(model_cost, 6),
            "failures": [f"{k}: {v}" for k, v in Counter(md["all_failures"]).items()] if md["all_failures"] else [],
        }

    # Print total cost
    print(f"\n  Total cost: ${_cost_guard.cumulative_cost:.4f} (budget: ${_cost_guard.budget:.2f})")

    # Write tuning log
    print(f"\n{'='*70}")
    print("Run complete. Edit tests/prompts/system_prompt.txt and re-run.")
    print(f"{'='*70}")

    try:
        desc = input("\nBrief description of what you changed (or Enter to skip): ").strip()
    except EOFError:
        desc = ""
    log_entry["change_description"] = desc

    TUNING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TUNING_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    print(f"Logged to {TUNING_LOG}")


if __name__ == "__main__":
    main()
