#!/bin/bash

set -Eeuo pipefail

cd ~/TaxBench-IN/Thesis_code

export GEMMA4_BACKEND=llamacpp
export LLAMACPP_BASE_URL=http://127.0.0.1:8080/v1

MODEL="ollama/gemma4-12b-ctx16k"
SERVER_URL="http://127.0.0.1:8080"

echo "Checking Gemma server..."

until curl -fsS "$SERVER_URL/health" >/dev/null; do
    echo "Waiting for Gemma..."
    sleep 5
done

echo "Gemma server is ready!"

for method in tool-call script zero-shot; do
    echo
    echo "=========================================="
    echo "Starting evaluation: $method"
    echo "=========================================="

    python tests/evaluate_llm.py \
        --model "$MODEL" \
        --method "$method" \
        --max-cases 569

    echo "Completed: $method"
done

echo
echo "=========================================="
echo "ALL THREE GEMMA EVALUATIONS COMPLETED!"
echo "=========================================="
