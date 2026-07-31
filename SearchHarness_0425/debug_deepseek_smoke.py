import argparse
import json
import os
import platform
import sys
from typing import Any, Dict, Optional

import requests


def _mask_secret(value: Optional[str]) -> str:
    if not value:
        return "<missing>"
    if len(value) <= 10:
        return value[:2] + "..." + value[-2:]
    return value[:6] + "..." + value[-4:]


def _print_kv(key: str, value: Any) -> None:
    print(f"{key}: {value}")


def _safe_prefix(text: str, limit: int) -> str:
    prefix = (text or "")[:limit]
    # PowerShell console may be GBK; keep output ASCII-safe.
    return prefix.encode("ascii", errors="backslashreplace").decode("ascii").replace("\n", "\\n")


def _get_proxies_snapshot() -> Dict[str, str]:
    keys = [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    ]
    return {k: v for k, v in ((k, os.environ.get(k)) for k in keys) if v}


def _clear_proxy_env() -> None:
    for k in [
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ]:
        os.environ.pop(k, None)


def _load_env_file(path: str) -> None:
    # Minimal .env loader to keep this script dependency-free.
    # Only sets keys that are currently missing from the environment.
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'").strip('"')
                if not k:
                    continue
                if os.environ.get(k):
                    continue
                os.environ[k] = v
    except FileNotFoundError:
        return
    except Exception:
        return


def _req(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    json_body: Optional[Dict[str, Any]] = None,
    timeout_s: int = 30,
) -> requests.Response:
    return requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        timeout=timeout_s,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test DeepSeek (OpenAI-compatible) API connectivity.")
    parser.add_argument("--no-proxy", action="store_true", help="Clear *_PROXY env vars inside this process.")
    parser.add_argument(
        "--env-file",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")),
        help="Path to a .env file to load if needed.",
    )
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "").strip() or "https://preview.llm.tenyunc.com/v1")
    parser.add_argument(
        "--model",
        default=(
            os.environ.get("ENTRY_POINT_MODEL")
            or os.environ.get("MODEL_NAME")
            or os.environ.get("MODEL")
            or "GLM-5.2"
        ).strip(),
    )
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    # Ensure OPENAI_* are available even when running this script standalone.
    if not (os.environ.get("OPENAI_API_KEY") or "").strip():
        _load_env_file(args.env_file)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    base_url = args.base_url.rstrip("/")
    model = args.model

    _print_kv("python", sys.version.split()[0])
    _print_kv("platform", f"{platform.system()} {platform.release()}")
    _print_kv("requests", getattr(requests, "__version__", "<unknown>"))
    _print_kv("base_url", base_url)
    _print_kv("model", model)
    _print_kv("openai_api_key", _mask_secret(api_key))

    proxies_before = _get_proxies_snapshot()
    _print_kv("proxy_env_before", json.dumps(proxies_before, ensure_ascii=True))

    if args.no_proxy:
        _clear_proxy_env()
        proxies_after = _get_proxies_snapshot()
        _print_kv("proxy_env_after", json.dumps(proxies_after, ensure_ascii=True))

    if not api_key:
        print("ERROR: OPENAI_API_KEY is missing.")
        return 2

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # 1) Models list (cheap GET)
    models_url = f"{base_url}/models"
    print(f"\n==> GET {models_url}")
    try:
        resp = _req("GET", models_url, headers=headers, timeout_s=args.timeout)
        print("status:", resp.status_code)
        print("body_prefix:", _safe_prefix(resp.text, 500))
    except Exception as e:
        print("ERROR during GET /models:", repr(e))

    # 2) Chat completion (minimal POST)
    chat_url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 8,
        "temperature": 0,
    }
    print(f"\n==> POST {chat_url}")
    try:
        resp = _req("POST", chat_url, headers=headers, json_body=payload, timeout_s=args.timeout)
        print("status:", resp.status_code)
        print("body_prefix:", _safe_prefix(resp.text, 800))
    except Exception as e:
        print("ERROR during POST /chat/completions:", repr(e))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
