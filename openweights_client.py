"""Open-weight runner status: Muse Spark Open and Muse Glimmer.

Neither model is hosted on the Meta Model API (Models page): both run on
your own hardware or a hosted provider through OpenAI-compatible HTTP
runtimes. Verified against the official Meta Model API docs
(https://dev.meta.ai/docs/) this session:

- Muse Spark Open: checkpoint e.g.
  ``meta-models/Muse-Spark-Open-816B-A42B-NVFP4``; runners vLLM (``vllm serve
  <repo>``), SGLang, TensorRT-LLM, Dynamo, llama.cpp, MLX
  (/docs/muse-spark-open/deploy). Validated NVFP4 run needs a 4-GPU
  Blackwell node; BF16 needs eight ranks. Hardware-heavy: do not set up
  without asking first.
- Muse Glimmer: 30B dense multimodal (``meta-models/Muse-Glimmer-30B``,
  bf16 ~60 GB, ~72 GB VRAM to serve; quantized GGUF
  ``meta-models/Muse-Glimmer-30B-GGUF`` 17-20 GB, e.g.
  ``Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf``). Runners vLLM, SGLang,
  llama.cpp (incl. laptops), ExecuTorch, Ollama (``ollama run
  muse-glimmer``), LM Studio (/docs/muse-glimmer, /get-the-model, /deploy).

This module never downloads weights and never starts a runner. It only
reports setup state, and when a runner base URL is configured it lists the
served models through the documented OpenAI-compatible ``GET /v1/models``
call. No key is involved; nothing here prints secrets.
"""

import os

import httpx

DOCS_SPARK_OPEN = "https://dev.meta.ai/docs/muse-spark-open/deploy"
DOCS_GLIMMER = "https://dev.meta.ai/docs/muse-glimmer/deploy"

MODELS = {
    "spark-open": {
        "label": "Muse Spark Open",
        "repo": "meta-models/Muse-Spark-Open-816B-A42B-NVFP4",
        "env_var": "SPARK_OPEN_BASE_URL",
        "runners": ["vLLM", "SGLang", "TensorRT-LLM", "Dynamo", "llama.cpp", "MLX"],
        "hardware": "Validated NVFP4 run needs a 4-GPU Blackwell node; BF16 needs eight ranks.",
        "serve_hint": "vllm serve meta-models/Muse-Spark-Open-816B-A42B-NVFP4",
        "docs": DOCS_SPARK_OPEN,
    },
    "glimmer": {
        "label": "Muse Glimmer",
        "repo": "meta-models/Muse-Glimmer-30B",
        "repo_quantized": "meta-models/Muse-Glimmer-30B-GGUF",
        "env_var": "GLIMMER_BASE_URL",
        "runners": ["vLLM", "SGLang", "llama.cpp", "ExecuTorch", "Ollama", "LM Studio"],
        "hardware": "bf16 ~60 GB weights, ~72 GB VRAM; quantized GGUF builds 17-20 GB.",
        "serve_hint": "ollama run muse-glimmer",
        "docs": DOCS_GLIMMER,
    },
}


def runner_status(model_key: str, timeout: float = 5.0) -> dict:
    """Report setup state for one open-weight model, probing only if configured.

    Raises ValueError for an unknown model key. Without a configured runner
    base URL this reports ``source: "setup-required"`` and performs no
    network call. With one it performs a single ``GET /v1/models`` listing.
    """
    if model_key not in MODELS:
        raise ValueError(f"unknown open-weight model: {model_key!r}")
    spec = MODELS[model_key]
    base_url = (os.environ.get(spec["env_var"]) or "").strip().rstrip("/")
    base = {
        "model": model_key,
        "label": spec["label"],
        "repo": spec["repo"],
        "runners": spec["runners"],
        "hardware": spec["hardware"],
        "serve_hint": spec["serve_hint"],
        "docs": spec["docs"],
    }
    if not base_url:
        return {
            **base,
            "source": "setup-required",
            "reachable": False,
            "served_models": [],
            "detail": (
                f"No runner configured: set {spec['env_var']} to a running "
                f"OpenAI-compatible server base URL (e.g. after "
                f"'{spec['serve_hint']}'). See {spec['docs']}."
            ),
        }
    try:
        response = httpx.get(f"{base_url}/models", timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        served = [
            str(item.get("id"))
            for item in payload.get("data", [])
            if isinstance(item, dict) and item.get("id")
        ]
    except Exception:
        return {
            **base,
            "source": "unreachable",
            "reachable": False,
            "served_models": [],
            "detail": f"Runner at {base_url} did not answer the /v1/models listing.",
        }
    return {
        **base,
        "source": "openweights-local",
        "reachable": True,
        "served_models": served,
        "detail": f"Runner at {base_url} answered.",
    }
