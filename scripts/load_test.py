"""A small load test for the API.

    python scripts/load_test.py --url http://localhost:8000 --requests 200
    python scripts/load_test.py --url http://localhost:8000 --path /api/v1/ai/chat/ --post

It is deliberately dependency-free (the standard library only), so it runs
anywhere the stack runs. The numbers it prints are the ones to watch after a
change: the median and the 95th percentile of the latency, and the error rate.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

#: The queries the assistant is asked — the realistic mix.
QUERIES = [
    "بهترین سیستم گیمینگ برای 1080p کدام است؟",
    "قیمت کارت گرافیک RTX 4070 SUPER چقدر است؟",
    "حافظه DDR5 چیست؟",
    "سوکت پردازنده رایزن ۷ ۸۰۰۰X3D چیست؟",
    "سیستم گیمینگ ۱۰۸۰p با بودجه ۵۰ میلیون پیشنهاد بده",
]


def percentile(values: list[float], fraction: float) -> float:
    """The `fraction` percentile of the values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))
    return ordered[index]


def call(url: str, *, post: bool, timeout: float) -> tuple[int, float, str]:
    """One request. Returns the status, the latency in ms and the error."""
    started = time.perf_counter()
    try:
        if post:
            body = json.dumps({"query": QUERIES[0], "stream": False}).encode()
            request = urllib.request.Request(
                url, data=body, headers={"Content-Type": "application/json"}
            )
        else:
            request = urllib.request.Request(
                url, headers={"Accept": "application/json"}
            )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status = response.status
        error = ""
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001 — any failure is a failed request
        status = 0
        error = str(exc)
    latency_ms = (time.perf_counter() - started) * 1000
    return status, latency_ms, error


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A small load test for the TechBase API."
    )
    parser.add_argument("--url", default="http://localhost:8000", help="the base URL")
    parser.add_argument(
        "--path", default="/api/v1/catalog/products/", help="the path to request"
    )
    parser.add_argument(
        "--requests", type=int, default=100, help="how many requests to make"
    )
    parser.add_argument("--concurrency", type=int, default=8, help="how many at a time")
    parser.add_argument(
        "--timeout", type=float, default=30.0, help="seconds per request"
    )
    parser.add_argument(
        "--post", action="store_true", help="POST to the chat endpoint instead of GET"
    )
    args = parser.parse_args()

    # Git Bash (MSYS) rewrites any argument that looks like an absolute path
    # into a Windows path — "/api/v1/chat/" becomes
    # "/Program Files/Git/api/v1/chat/". The path is therefore assembled here
    # from a leading dot (which the shell leaves alone) and the separator is
    # put back afterwards.
    base = args.url
    path = args.path
    if not path.startswith(("http", ".")):
        path = "." + path
    path = path.removeprefix(".")
    if not path.startswith("/"):
        path = "/" + path
    if len(base) > 2 and base[1] == ":" and base[0].isalpha():
        base = f"http://{base}"
    url = base.rstrip("/") + path
    print(f"-> {args.requests} requests to {url} ({args.concurrency} at a time)")

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        results = list(
            pool.map(
                lambda _: call(url, post=args.post, timeout=args.timeout),
                range(args.requests),
            )
        )
    total_seconds = time.perf_counter() - started

    latencies = [latency for _, latency, _ in results]
    errors = [error for _, _, error in results if error]
    statuses: dict[int, int] = {}
    for status, _, _ in results:
        statuses[status] = statuses.get(status, 0) + 1

    print()
    print(f"total time     : {total_seconds:.2f}s")
    print(f"throughput     : {len(results) / total_seconds:.1f} req/s")
    print(f"median         : {statistics.median(latencies):.0f} ms")
    print(f"95th percentile: {percentile(latencies, 0.95):.0f} ms")
    print(f"max            : {max(latencies):.0f} ms")
    print(f"errors         : {len(errors)} ({len(errors) / len(results):.1%})")
    print(f"statuses       : {statuses}")
    if errors:
        print(f"first error    : {errors[0]}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
