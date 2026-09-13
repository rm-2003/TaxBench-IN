# Model Availability Status

Last updated: 2026-04-23

## Final model list (6 models)

| Tier | Model | Type | Parse Rate (tuning) | Score (tuning) | Notes |
|------|-------|------|-----------|-------|-------|
| 1 — High | `openai/gpt-oss-120b:free` | Free | 2/2 (100%) | 55.4% | Reliable, fast |
| 1 — High | `tencent/hy3-preview:free` | Free | 2/2 (100%) | 47.3% | JSON mode not supported (fallback works) |
| 2 — Mid | `deepseek/deepseek-chat-v3-0324` | Paid | — | — | ~$0.50-1.00 for 569 cases |
| 2 — Mid | `meta-llama/llama-3.3-70b-instruct` | Paid | — | — | ~$0.25-0.45 for 569 cases |
| 3 — Low | `nvidia/nemotron-nano-9b-v2:free` | Free | 5/5 (100%) | 38.9% | Reasoning model — needs high max_tokens |
| 3 — Low | `openai/gpt-oss-20b:free` | Free | 2/2 (100%) | 39.2% | Had control-char issue (fixed in extract_json) |

## Dropped models

| Model | Reason |
|-------|--------|
| `google/gemma-4-31b-it:free` | Persistent 429 upstream rate limit (Google AI Studio) |
| `nvidia/nemotron-3-super-120b-a12b:free` | Returns empty responses (choices=None) |
| `meta-llama/llama-3.3-70b-instruct:free` | 429 upstream rate limit (Venice); replaced by paid version |
| `qwen/qwen3-coder:free` | 429 rate limited |

## Cost estimates (zero-shot, 569 cases)

| Model | Prompt $/1M | Completion $/1M | Est. total |
|-------|------------|----------------|------------|
| deepseek-chat-v3-0324 | $0.27 | $1.10 | ~$0.50-1.00 |
| llama-3.3-70b-instruct | $0.10 | $0.32 | ~$0.25-0.45 |
| Free models | $0 | $0 | $0 |

Total estimated budget for all 6 models × zero-shot: ~$1-2
