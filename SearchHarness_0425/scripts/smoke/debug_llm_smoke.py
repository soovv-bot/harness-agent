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
    parser = argparse.ArgumentParser(description="Smoke test LLM (OpenAI-compatible) API connectivity.")
    parser.add_argument("--no-proxy", action="store_true", help="Clear *_PROXY env vars inside this process.")
    parser.add_argument(
        "--env-file",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")),
        help="Path to a .env file to load if needed.",
    )
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--verify-thinking", action="store_true",
                        help="Also verify reasoning_effort switch: send one 'minimal' and one default request, "
                             "compare reasoning_tokens to confirm the thinking switch takes effect at API layer.")
    args = parser.parse_args()

    # Always load .env (dotenv does not override existing shell env vars by default).
    _load_env_file(args.env_file)

    api_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    base_url = (args.base_url or os.environ.get("OPENAI_BASE_URL") or os.environ.get("API_BASE") or "https://preview.llm.tenyunc.com/v1").strip().rstrip("/")
    model = (args.model or os.environ.get("ENTRY_POINT_MODEL") or os.environ.get("MODEL_NAME") or os.environ.get("MODEL") or "").strip()

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

    if args.verify_thinking:
        _verify_thinking(chat_url, headers, model, args.timeout)

    return 0


def _verify_thinking(chat_url: str, headers: dict, model: str, timeout_s: int) -> None:
    """Send one 'none' and one default chat request, compare reasoning_tokens.

    Confirms the reasoning_effort switch is honored by the endpoint:
      - 'none' branch should produce reasoning_tokens == 0 (or absent)
      - default branch should produce reasoning_tokens > 0 (for reasoning models)
    """
    print("\n==> [verify-thinking] comparing reasoning_effort=minimal vs default")
    base_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Think briefly, then reply with: ok"}],
        "max_tokens": 64,
        "temperature": 0,
    }

    def _extract_reasoning_tokens(body: dict) -> int:
        try:
            return int(body.get("usage", {}).get("completion_tokens_details", {}).get("reasoning_tokens", 0))
        except (TypeError, ValueError):
            return 0

    results = {}
    # OpenAI standard: reasoning_effort is a top-level kwarg. No extra_body injection.
    for label, extra in (("minimal", {"reasoning_effort": "minimal"}),
                        ("default", {})):
        payload = dict(base_payload)
        payload.update(extra)
        print(f"  [{label}] POST ...")
        try:
            resp = _req("POST", chat_url, headers=headers, json_body=payload, timeout_s=timeout_s)
            body = json.loads(resp.text) if resp.text else {}
            rt = _extract_reasoning_tokens(body)
            ct = int(body.get("usage", {}).get("completion_tokens", 0))
            print(f"  [{label}] status={resp.status_code} reasoning_tokens={rt} completion_tokens={ct}")
            results[label] = {"status": resp.status_code, "reasoning_tokens": rt, "completion_tokens": ct}
        except Exception as e:
            print(f"  [{label}] ERROR: {e!r}")
            results[label] = {"error": repr(e)}

    # Verdict
    none_rt = results.get("minimal", {}).get("reasoning_tokens")
    default_rt = results.get("default", {}).get("reasoning_tokens")
    if none_rt is not None and default_rt is not None:
        if none_rt == 0 and default_rt > 0:
            print("  VERDICT: PASS — reasoning_effort=minimal disables thinking, default enables it")
        elif none_rt == 0 and default_rt == 0:
            print("  VERDICT: CHECK — both branches reasoning_tokens=0 (model may not be a reasoning model, "
                  "or endpoint ignores reasoning_effort)")
        elif none_rt < default_rt:
            print(f"  VERDICT: PASS — minimal={none_rt} < default={default_rt} (effort controls reasoning budget)")
        else:
            print(f"  VERDICT: CHECK — minimal={none_rt} default={default_rt} (unexpected; endpoint may not honor "
                  "reasoning_effort)")
    else:
        print("  VERDICT: CHECK — one or both branches errored")


if __name__ == "__main__":
    raise SystemExit(main())
