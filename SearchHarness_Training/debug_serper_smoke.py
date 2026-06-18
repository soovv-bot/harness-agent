import json
import os

import requests
from dotenv import load_dotenv


def main() -> None:
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"), override=True)
    for key in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]:
        os.environ.pop(key, None)

    api_key = os.getenv("SERPER_API_KEY")
    print("has_key:", bool(api_key))
    print("key_prefix:", api_key[:6] if api_key else None)
    print("HTTP_PROXY:", os.getenv("HTTP_PROXY"))
    print("HTTPS_PROXY:", os.getenv("HTTPS_PROXY"))

    payload = {"q": "Whitesnake band", "num": 3}
    response = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": api_key or "", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )

    print("status_code:", response.status_code)
    print("raw_prefix:", response.text[:500])
    try:
        data = response.json()
    except Exception as exc:
        print("json_error:", repr(exc))
        return

    print("credits:", data.get("credits"))
    print("searchParameters:", data.get("searchParameters"))
    for idx, item in enumerate(data.get("organic", [])[:3], start=1):
        print(f"organic_{idx}_title:", item.get("title"))
        print(f"organic_{idx}_link:", item.get("link"))


if __name__ == "__main__":
    main()
