from __future__ import annotations

import json
import os
from typing import List

import requests
from dotenv import load_dotenv


def call_serper(query: str) -> None:
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        print("SERPER_API_KEY is not set")
        return

    url = "https://google.serper.dev/search"
    payload = {"q": query}
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    print("=" * 80)
    print("QUERY:", query)
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        print("STATUS:", response.status_code)
        print("BODY:", response.text[:2000])
    except Exception as exc:
        print("EXCEPTION:", repr(exc))


def main() -> None:
    load_dotenv()
    queries: List[str] = [
        '"never been read to as a child" poet interview',
        '"never read to as a child" poet interview mental health',
        "never been read to as a child poet interview",
        "never read to as a child poet interview mental health",
        '"Jason Kyle Howard married to Silas House"',
        "Jason Kyle Howard married to Silas House",
    ]
    for query in queries:
        call_serper(query)


if __name__ == "__main__":
    main()
