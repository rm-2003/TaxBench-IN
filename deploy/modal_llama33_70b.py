"""Serve Llama 3.3 70B Instruct on Modal with vLLM (OpenAI-compatible API).

Deploy:   ~/.venvs/modal/bin/modal deploy deploy/modal_llama33_70b.py
Stop:     ~/.venvs/modal/bin/modal app stop llama33-70b-vllm

The harness reaches it through the `modal/` route in tests/evaluate_llm.py,
which reads MODAL_VLLM_BASE_URL (the deployed URL + "/v1") and
MODAL_VLLM_API_KEY from the environment. Requires two Modal secrets:
`huggingface` (HF_TOKEN with access to the gated Meta repo) and
`vllm-api-key` (VLLM_API_KEY, the same value as MODAL_VLLM_API_KEY).

Full bf16 weights on 2x H100 80GB with tensor parallelism, so results are for
the released model, not a quantised variant. Model revision and vLLM version
are pinned for reproducibility.
"""

import os
import subprocess

import modal

MODEL = "meta-llama/Llama-3.3-70B-Instruct"
REVISION = "6f6073b423013f6a7d4d9f39144961bfbfbc386b"  # main as of 2024-12-21
SERVED_NAME = "llama-3.3-70b-instruct"
VLLM_VERSION = "0.32.0"
GPU = os.environ.get("MODAL_GPU", "H100:2")  # e.g. "A100-80GB:2"; count must match TP below
TP = GPU.split(":")[1] if ":" in GPU else "1"
MAX_MODEL_LEN = 32768  # tool-call conversations reach ~20k tokens; 128k is not needed
PORT = 8000

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(f"vllm=={VLLM_VERSION}", "huggingface_hub[hf_transfer]")
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# Weights (~140 GB) are downloaded once into a persistent volume, not on every start.
hf_cache = modal.Volume.from_name("hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("vllm-cache", create_if_missing=True)

app = modal.App("llama33-70b-vllm")


@app.function(
    image=image,
    gpu=GPU,
    secrets=[modal.Secret.from_name("huggingface"), modal.Secret.from_name("vllm-api-key")],
    volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
    timeout=24 * 60 * 60,
    scaledown_window=10 * 60,  # shut the GPUs down after 10 idle minutes
)
@modal.concurrent(max_inputs=64)
@modal.web_server(port=PORT, startup_timeout=40 * 60)
def serve():
    cmd = [
        "vllm", "serve", MODEL,
        "--revision", REVISION,
        "--served-model-name", SERVED_NAME,
        "--tensor-parallel-size", TP,
        "--max-model-len", str(MAX_MODEL_LEN),
        "--enable-auto-tool-choice",
        "--tool-call-parser", "llama3_json",
        "--host", "0.0.0.0",
        "--port", str(PORT),
        "--api-key", "$VLLM_API_KEY",
    ]
    subprocess.Popen(" ".join(cmd), shell=True)
