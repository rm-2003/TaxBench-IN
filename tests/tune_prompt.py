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
import time
from collections import Counter
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
    "weak":   "nvidia/nemotron-nano-9b-v2:free",
    "mid":    "google/gemma-4-31b-it:free",
    "strong": "meta-llama/llama-3.3-70b-instruct:free",
}

# ---------------------------------------------------------------------------
# Constants (mirror evaluate_llm.py)
# ---------------------------------------------------------------------------
MAX_TOOL_ROUNDS = 20
MAX_SCRIPT_RETRIES = 3
SCRIPT_TIMEOUT = 20
TOLERANCE = 0.01
DELAY_BETWEEN_CALLS = 1.0

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
def extract_json(text):
    """Extract the first valid JSON object from text."""
    # Try the raw text first
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    if not text:
        return None
    # Try stripping markdown fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... } block
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
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
class CostGuard:
    """Checks that API calls remain free.  Halts if any cost is detected."""

    def __init__(self):
        self.cumulative_cost = 0.0

    def check(self, response):
        """Inspect an API response's usage block. Raises if cost > 0."""
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        cost = getattr(usage, "cost", None)
        if cost is None and isinstance(usage, dict):
            cost = usage.get("cost")
        if cost is not None and float(cost) > 0:
            self.cumulative_cost += float(cost)
            raise RuntimeError(
                f"NON-ZERO COST detected: ${float(cost):.6f} this call, "
                f"${self.cumulative_cost:.6f} cumulative. Halting to prevent charges. "
                f"Ensure you are using ':free' model endpoints."
            )


# ---------------------------------------------------------------------------
# Method runners
# ---------------------------------------------------------------------------
_cost_guard = CostGuard()


def run_zero_shot(client, model, system_prompt, input_json):
    messages = build_messages("zero-shot", system_prompt, input_json)
    resp = client.chat.completions.create(model=model, messages=messages, temperature=0)
    _cost_guard.check(resp)
    raw = get_response_text(resp.choices[0].message)
    return extract_json(raw), raw


def run_script(client, model, system_prompt, input_json):
    messages = build_messages("script", system_prompt, input_json)
    raw_responses = []

    for attempt in range(1 + MAX_SCRIPT_RETRIES):
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0)
        _cost_guard.check(resp)
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
        resp = client.chat.completions.create(
            model=model, messages=messages,
            tools=[CALCULATE_TOOL], temperature=0,
        )
        _cost_guard.check(resp)
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
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Interactive prompt tuning for LLM tax benchmark")
    parser.add_argument("--method", choices=["zero-shot", "script", "tool-call"], default="zero-shot")
    parser.add_argument("--cases", type=int, default=5)
    parser.add_argument("--seed", type=int, default=None, help="Random seed for case selection")
    args = parser.parse_args()

    client = get_client()
    system_prompt = load_system_prompt()
    prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:8]

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

    aborted = False
    for tier, model in TUNING_MODELS.items():
        if aborted:
            break

        print(f"\n{'─'*70}")
        print(f"  [{tier.upper()}] {model}")
        print(f"{'─'*70}")

        parse_ok = 0
        total_score = 0
        all_failures = []
        all_key_issues = []

        for i, case in enumerate(cases):
            print(f"\n  Case {i+1}/{len(cases)}: {case['file']}")
            print(f"    Desc: {case['description'][:80]}...")

            try:
                if args.method == "zero-shot":
                    output, raw = run_zero_shot(client, model, system_prompt, case["input"])
                elif args.method == "script":
                    output, raw = run_script(client, model, system_prompt, case["input"])
                elif args.method == "tool-call":
                    output, raw = run_tool_call(client, model, system_prompt, case["input"])
            except RuntimeError as e:
                # Cost guard triggered — abort everything
                print(f"\n    COST GUARD: {e}")
                print("    ABORTING entire tuning run to prevent charges.")
                aborted = True
                break
            except Exception as e:
                print(f"    API ERROR: {e}")
                all_failures.extend(["api_error"])
                continue

            if output is not None:
                parse_ok += 1
                missing, extra = check_keys(output)
                scores, sc_total, sc_max = score_case(case["expected"], output)
                total_score += sc_total

                print(f"    Parse:  OK")
                print(f"    Score:  {sc_total}/{sc_max} ({sc_total/sc_max*100:.1f}%)")
                if missing:
                    print(f"    Missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}")
                    all_key_issues.extend(missing)
                if extra:
                    print(f"    Extra keys:   {extra[:5]}{'...' if len(extra) > 5 else ''}")
            else:
                print(f"    Parse:  FAIL")
                failure_pats = detect_failure_patterns(raw)
                if failure_pats:
                    print(f"    Patterns: {failure_pats}")
                all_failures.extend(failure_pats if failure_pats else ["unknown"])
                preview = raw[:300].replace("\n", "\\n")
                print(f"    Raw preview: {preview}")

            time.sleep(DELAY_BETWEEN_CALLS)

        n = len(cases)
        if parse_ok > 0 or all_failures:
            mean_score = total_score / max(parse_ok, 1)
            print(f"\n  --- {tier.upper()} SUMMARY ({model}) ---")
            print(f"  Parse rate:  {parse_ok}/{n} ({parse_ok/n*100:.0f}%)")
            print(f"  Mean score (parsed): {mean_score:.1f}/37 ({mean_score/37*100:.1f}%)")
            if all_failures:
                counts = Counter(all_failures)
                print(f"  Failure patterns: {dict(counts)}")
            if all_key_issues:
                key_counts = Counter(all_key_issues)
                top_missing = key_counts.most_common(5)
                print(f"  Top missing keys: {top_missing}")

            log_entry["results"][model] = {
                "tier": tier,
                "parse_rate": parse_ok / n,
                "mean_score_parsed": round(mean_score / 37, 4),
                "failures": [f"{k}: {v}" for k, v in Counter(all_failures).items()] if all_failures else [],
            }

    if aborted:
        print(f"\n{'='*70}")
        print("RUN ABORTED — non-zero cost detected. Check your model endpoints.")
        print(f"{'='*70}")
        sys.exit(1)

    # Write tuning log
    print(f"\n{'='*70}")
    print("Run complete. Edit tests/prompts/system_prompt.txt and re-run.")
    print(f"{'='*70}")

    desc = input("\nBrief description of what you changed (or Enter to skip): ").strip()
    log_entry["change_description"] = desc

    TUNING_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TUNING_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    print(f"Logged to {TUNING_LOG}")


if __name__ == "__main__":
    main()
