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

import json
import os
import time

import httpx

DOCS_SPARK_OPEN = "https://dev.meta.ai/docs/muse-spark-open/deploy"
DOCS_GLIMMER = "https://dev.meta.ai/docs/muse-glimmer/deploy"

MODELS = {
    "spark-open": {
        "label": "Muse Spark Open",
        "repo": "meta-models/Muse-Spark-Open-816B-A42B-NVFP4",
        "env_var": "SPARK_OPEN_BASE_URL",
        "key_env_var": "SPARK_OPEN_API_KEY",
        "model_env_var": "SPARK_OPEN_MODEL",
        "default_serve_as": "meta-models/Muse-Spark-Open-816B-A42B-NVFP4",
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
        "key_env_var": "GLIMMER_API_KEY",
        "model_env_var": "GLIMMER_MODEL_NAME",
        "default_serve_as": "muse-glimmer",
        "runners": ["vLLM", "SGLang", "llama.cpp", "ExecuTorch", "Ollama", "LM Studio"],
        "hardware": "bf16 ~60 GB weights, ~72 GB VRAM; quantized GGUF builds 17-20 GB.",
        "serve_hint": "ollama run muse-glimmer",
        "docs": DOCS_GLIMMER,
    },
}


def _serve_as(model_key: str) -> str:
    """Effective served-model name: env override or the documented default."""
    spec = MODELS[model_key]
    return (os.environ.get(spec["model_env_var"]) or "").strip() or spec["default_serve_as"]


def build_severity_prompt(findings: list[dict]) -> str:
    """Build a deterministic disruption-classification prompt from findings."""
    lines = [
        "Classify this freight disruption severity as LOW, MODERATE, HIGH,",
        "or CRITICAL, then one sentence why. Synthetic demo findings:",
    ]
    for finding in findings:
        lines.append(
            f"- {finding['mode']}: {finding['status']}, "
            f"+{finding['delay_hours']}h delay."
        )
    return "\n".join(lines)


# Fixed critique schema for the route challenge. Every key is required:
# agree_with_top_pick (bool), preferred_option_id (one of the ranked ids),
# concerns (list of short strings), confidence (0..1 float).
CRITIQUE_SCHEMA_KEYS = (
    "agree_with_top_pick",
    "preferred_option_id",
    "concerns",
    "confidence",
)


def build_critique_prompt(
    case_label: str, findings: list[dict], ranked_options: list[dict]
) -> str:
    """Build a deterministic prompt asking for a strict-JSON ranking critique."""
    valid_ids = ", ".join(f'"{o["option_id"]}"' for o in ranked_options)
    lines = [
        f"Critique this freight reroute ranking for: {case_label}.",
        "Output ONLY strict JSON, no markdown, no commentary:",
        '{"agree_with_top_pick": bool, "preferred_option_id": ..., '
        '"concerns": [...], "confidence": 0..1}.',
        f'"preferred_option_id" must be one of: {valid_ids}.',
        '"concerns" lists at most three short strings (empty array is fine).',
        '"confidence" is your confidence from 0 to 1.',
        "Your critique is advisory; the deterministic ranking stays authoritative.",
        "Synthetic demo data. Findings:",
    ]
    for finding in findings:
        lines.append(
            f"- {finding['mode']}: {finding['status']}, "
            f"+{finding['delay_hours']}h delay, "
            f"cost ${finding['cost_usd']}, "
            f"on-time {finding['on_time_probability']}."
        )
    lines.append("Ranking to critique:")
    for option in ranked_options:
        lines.append(
            f"Rank {option['rank']}: {option['option_id']} "
            f"({option['title']}), score {option['score']}, "
            f"cost ${option['cost_usd']}, "
            f"saves {option['time_saved_hours']}h, "
            f"on-time {option['on_time_probability']}, "
            f"confidence {option['confidence']}."
        )
    return "\n".join(lines)


def parse_critique_response(text: str, valid_option_ids: list[str]) -> dict:
    """Parse and strictly validate a strict-JSON critique reply.

    Raises ValueError on any schema violation: unparsable JSON, a missing
    or mistyped key, an unknown preferred option id, or a confidence
    outside 0..1.
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        fence_lines = cleaned.splitlines()[1:]
        if fence_lines and fence_lines[-1].strip().startswith("```"):
            fence_lines = fence_lines[:-1]
        cleaned = "\n".join(fence_lines).strip()
    try:
        payload = json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"critique reply is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("critique reply must be a JSON object")
    agree = payload.get("agree_with_top_pick")
    preferred = payload.get("preferred_option_id")
    concerns = payload.get("concerns")
    confidence = payload.get("confidence")
    if not isinstance(agree, bool):
        raise ValueError("'agree_with_top_pick' must be a boolean")
    if preferred not in valid_option_ids:
        raise ValueError("'preferred_option_id' must be one of the ranked options")
    if not isinstance(concerns, list) or any(
        not isinstance(item, str) for item in concerns
    ):
        raise ValueError("'concerns' must be a list of strings")
    if (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not 0 <= confidence <= 1
    ):
        raise ValueError("'confidence' must be a number from 0 to 1")
    return {
        "agree_with_top_pick": agree,
        "preferred_option_id": preferred,
        "concerns": concerns,
        "confidence": float(confidence),
    }


def _extract_usage(usage: object) -> dict | None:
    """Pull token counts from an OpenAI-compatible usage block, if present."""
    if not isinstance(usage, dict):
        return None
    counts = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = usage.get(key)
        counts[key] = (
            value if isinstance(value, int) and not isinstance(value, bool) else None
        )
    if all(value is None for value in counts.values()):
        return None
    return counts


def complete_with_metrics(
    model_key: str, prompt: str, timeout: float = 300.0
) -> dict:
    """Run one chat completion, also reporting latency and token usage.

    Same runner rules as :func:`generate_text` (ValueError on an unknown
    model key, ``setup-required`` without a base URL, ``unreachable`` on
    any call failure), plus ``latency_ms`` for every attempted call and
    the OpenAI-compatible ``usage`` block when the runner returns one.
    """
    if model_key not in MODELS:
        raise ValueError(f"unknown open-weight model: {model_key!r}")
    spec = MODELS[model_key]
    base_url = (os.environ.get(spec["env_var"]) or "").strip().rstrip("/")
    if not base_url:
        return {
            "model": model_key,
            "source": "setup-required",
            "text": None,
            "latency_ms": None,
            "usage": None,
            "detail": (
                f"No runner configured: set {spec['env_var']} to a running "
                f"OpenAI-compatible server base URL. See {spec['docs']}."
            ),
        }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(spec["key_env_var"])
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    start = time.perf_counter()
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": _serve_as(model_key),
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        text = str(payload["choices"][0]["message"]["content"])
        usage = _extract_usage(payload.get("usage"))
    except Exception:
        return {
            "model": model_key,
            "source": "unreachable",
            "text": None,
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "usage": None,
            "detail": f"Runner at {base_url} did not complete the completion call.",
        }
    return {
        "model": model_key,
        "source": "openweights-local",
        "text": text,
        "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        "usage": usage,
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
        "model_name": _serve_as(model_key),
        "api_key_set": bool(os.environ.get(spec["key_env_var"])),
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
        # Hosted partners (e.g. Together AI) require the key even for the
        # listing; local runners typically need none, so send it only if set.
        list_kwargs: dict = {"timeout": timeout}
        list_key = os.environ.get(spec["key_env_var"])
        if list_key:
            list_kwargs["headers"] = {"Authorization": f"Bearer {list_key}"}
        response = httpx.get(f"{base_url}/models", **list_kwargs)
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


def generate_text(model_key: str, prompt: str, timeout: float = 300.0) -> dict:
    """Run one chat completion against the configured runner.

    Raises ValueError for an unknown model key. Without a configured runner
    base URL this reports ``source: "setup-required"`` and performs no
    network call. The optional provider key is sent as a Bearer header and
    never logged or returned; local runners typically need none.
    """
    if model_key not in MODELS:
        raise ValueError(f"unknown open-weight model: {model_key!r}")
    spec = MODELS[model_key]
    base_url = (os.environ.get(spec["env_var"]) or "").strip().rstrip("/")
    if not base_url:
        return {
            "model": model_key,
            "source": "setup-required",
            "text": None,
            "detail": (
                f"No runner configured: set {spec['env_var']} to a running "
                f"OpenAI-compatible server base URL. See {spec['docs']}."
            ),
        }
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get(spec["key_env_var"])
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        response = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": _serve_as(model_key),
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        text = str(response.json()["choices"][0]["message"]["content"])
    except Exception:
        return {
            "model": model_key,
            "source": "unreachable",
            "text": None,
            "detail": f"Runner at {base_url} did not complete the completion call.",
        }
    return {"model": model_key, "source": "openweights-local", "text": text}
