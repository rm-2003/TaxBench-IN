# Plan: Prompt Tuning Guidelines

Targeted improvements to maximise JSON adherence across all model tiers without adding tax-logic hints.

---

## Guideline 1: Repeat JSON instruction at the tail of the prompt

Models weight the end of the prompt more heavily. The schema definition in the middle gets "diluted" — end with a hard reminder:

```
Your entire response must be a single JSON object.
Begin your response with { and end with }. Nothing else.
```

**Applied to**: `tests/prompts/system_prompt.txt` — appended after the schema block.

---

## Guideline 2: Add a negative example for markdown fencing

Models RLHF'd to be "helpful" reflexively add fences. Showing the wrong pattern explicitly suppresses it:

```
WRONG: ```json { ... } ```
CORRECT: { ... }
```

**Applied to**: `tests/prompts/system_prompt.txt` — added in the tail section.

---

## Guideline 3: Think-then-respond separator for weaker models

Weaker models (9B, 20B) may need scratchpad space. Forcing them to externalise reasoning before the JSON keeps the JSON clean:

```
If you need to reason, do so inside <think></think> tags before the JSON.
Your response after the closing </think> tag must be only the JSON object.
```

`extract_json()` already handles this since it finds the first `{` after any preamble.

**Applied to**: `tests/prompts/system_prompt.txt` — added in the tail section.

---

## Guideline 4: Forbid common partial-output patterns by name

Small models frequently open with "Here is the computed tax breakdown:" — calling it out by name suppresses it:

```
Do not include any explanation after the closing }.
Do not say "Here is the JSON" or anything similar before the {.
```

**Applied to**: `tests/prompts/system_prompt.txt` — added in the tail section.

---

## Guideline 5: Use `response_format: {"type": "json_object"}` in API calls

OpenRouter forwards this to models that support it. Zero-effort, catches a large fraction of formatting failures. Wrap in try/except since some models/providers silently ignore or error on it.

**Applied to**: `tests/evaluate_llm.py` and `tests/tune_prompt.py` — added to all `client.chat.completions.create()` calls with fallback on error.
