"""In-process request metrics, exposed as JSON at /metrics.

Deliberately dependency-free: counters plus a bounded latency reservoir per
route. In production these would be StatsD/DogStatsD emissions to Datadog —
the names below follow that convention so the swap is mechanical.
"""

import threading
from collections import defaultdict, deque


class Metrics:
    def __init__(self, reservoir_size: int = 500) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self._latencies: dict[str, deque[float]] = defaultdict(
            lambda: deque(maxlen=reservoir_size)
        )

    def incr(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counters[name] += value

    def observe_latency(self, route: str, duration_ms: float) -> None:
        with self._lock:
            self._latencies[route].append(duration_ms)

    def snapshot(self) -> dict:
        with self._lock:
            latencies = {}
            for route, samples in self._latencies.items():
                ordered = sorted(samples)
                n = len(ordered)
                latencies[route] = {
                    "count": n,
                    "p50_ms": round(ordered[n // 2], 1),
                    "p99_ms": round(ordered[min(n - 1, int(n * 0.99))], 1),
                }
            return {"counters": dict(self._counters), "request_latency": latencies}


METRICS = Metrics()
