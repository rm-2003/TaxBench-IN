#!/bin/bash
#SBATCH --job-name=navya_2024A7PS0594P_taxbenchin
#SBATCH --partition=gpu-3day
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --output=deepseek_%j.out
#SBATCH --error=deepseek_%j.err

set -Ee -o pipefail

cd ~/TaxBench-IN/Thesis_code

echo "=========================================="
echo "DeepSeek R1 Distill 70B - TaxBench-IN"
echo "Job ID: $SLURM_JOB_ID"
echo "Host: $(hostname)"
echo "Allocated GPUs: $CUDA_VISIBLE_DEVICES"
echo "=========================================="

source /nfs_home/software/miniconda/etc/profile.d/conda.sh
conda activate gptoss

# Load CUDA
module load cuda/12.8
export LD_LIBRARY_PATH=/nfs_home/software/install/cuda/12.8/lib64:$LD_LIBRARY_PATH

# Configure evaluator
export LLAMACPP_BASE_URL=http://127.0.0.1:8082/v1

MODEL="llamacpp/deepseek-r1-distill-70b"
SERVER_URL="http://127.0.0.1:8082"

# Start DeepSeek server
../llama.cpp/build-gcc12/bin/llama-server \
    -m ../models/deepseek-r1-distill-70b/DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf \
    --host 127.0.0.1 \
    --port 8082 \
    -c 16384 \
    -ngl 99 \
    --split-mode none \
    --jinja \
    --parallel 1 \
    > deepseek_server.log 2>&1 &

SERVER_PID=$!

# Stop server when the job exits
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

# Wait for server readiness
echo "Waiting for DeepSeek server..."

for i in {1..180}; do
    if curl -fsS "$SERVER_URL/health" >/dev/null; then
        echo "DeepSeek is ready!"
        break
    fi

    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "ERROR: DeepSeek server exited unexpectedly."
        tail -n 80 deepseek_server.log
        exit 1
    fi

    if [ "$i" -eq 180 ]; then
        echo "ERROR: Server startup timed out."
        tail -n 80 deepseek_server.log
        exit 1
    fi

    sleep 5
done

# Run all evaluation methods sequentially
for method in script zero-shot; do
    echo ""
    echo "=========================================="
    echo "Starting evaluation: $method"
    echo "=========================================="

    python tests/evaluate_llm.py \
        --model "$MODEL" \
        --method "$method" \
        --max-cases 569

    echo "Finished evaluation: $method"
done

echo "=========================================="
echo "ALL DEEPSEEK EVALUATIONS COMPLETED"
echo "=========================================="
