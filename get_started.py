
import modal
import os
import subprocess
import time
import urllib.request

app = modal.App("taxbench-deepseek")

volume = modal.Volume.from_name("taxbench-models")

MODEL_PATH = (
    "/models/deepseek-r1-70b/"
    "DeepSeek-R1-Distill-Llama-70B-Q4_K_M.gguf"
)

MODEL_NAME = "deepseek-r1-70b"

# Ollama installation shared by both functions.
image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "zstd", "pciutils")
    .run_commands(
        "curl -fsSL https://ollama.com/install.sh | sh"
    )
)


# --------------------------------------------------
# STAGE 1: One-time GGUF import (CPU only)
# --------------------------------------------------

@app.function(
    image=image,
    volumes={"/models": volume},
    cpu=8,
    memory=32768,
    timeout=86400,
    max_containers=1,
)
def prepare_model():

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(MODEL_PATH)

    env = os.environ.copy()
    env["OLLAMA_MODELS"] = "/models/ollama"
    env["OLLAMA_HOST"] = "127.0.0.1:11434"

    print("Starting Ollama for model import...")

    server = subprocess.Popen(
        ["ollama", "serve"],
        env=env,
    )

    try:
        # Wait for Ollama to start.
        for _ in range(120):
            try:
                urllib.request.urlopen(
                    "http://127.0.0.1:11434/api/tags",
                    timeout=2,
                )
                break
            except Exception:
                time.sleep(2)
        else:
            raise RuntimeError("Ollama failed to start")

        # Skip import if the model already exists.
        existing = subprocess.run(
            ["ollama", "show", MODEL_NAME],
            env=env,
            capture_output=True,
        )

        if existing.returncode == 0:
            print("Model already imported. Skipping.")
        else:
            modelfile = "/tmp/Modelfile"

            with open(modelfile, "w") as f:
                f.write(
                    f"FROM {MODEL_PATH}\n"
                    "PARAMETER num_ctx 16384\n"
                )

            print("Importing DeepSeek GGUF into Ollama...")

            subprocess.run(
                [
                    "ollama",
                    "create",
                    MODEL_NAME,
                    "-f",
                    modelfile,
                ],
                env=env,
                check=True,
            )

            print("DeepSeek model imported successfully!")

        # Persist Ollama's model store.
        volume.commit()
        print("Volume changes committed.")

    finally:
        server.terminate()
        server.wait(timeout=30)


# --------------------------------------------------
# STAGE 2: GPU inference server
# --------------------------------------------------

@app.function(
    image=image,
    gpu="A100-80GB",
    volumes={"/models": volume},
    cpu=8,
    memory=32768,
    timeout=86400,
    startup_timeout=900,
    max_containers=1,
    scaledown_window=300,
)
@modal.web_server(
    11434,
    startup_timeout=900,
    requires_proxy_auth=True,
)
def ollama_server():

    env = os.environ.copy()

    env["OLLAMA_MODELS"] = "/models/ollama"
    env["OLLAMA_HOST"] = "0.0.0.0:11434"
    env["OLLAMA_CONTEXT_LENGTH"] = "16384"
    env["OLLAMA_NUM_PARALLEL"] = "1"
    env["OLLAMA_MAX_LOADED_MODELS"] = "1"

    print("Starting Ollama inference server...")

    subprocess.Popen(
        ["ollama", "serve"],
        env=env,
    )

    print("Ollama server process started.")
