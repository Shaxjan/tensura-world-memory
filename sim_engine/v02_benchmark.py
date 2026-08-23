from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path

from v02_engine import SimulationV02
from v02_seed import seed_blumund_v02


def benchmark(iterations: int = 200) -> dict[str, float]:
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "bench.db"
        seed_blumund_v02(db)
        with SimulationV02(db) as sim:
            samples = []
            for i in range(iterations):
                start = time.perf_counter()
                with sim.db:
                    sim.event("benchmark_checkpoint", payload={"i": i})
                samples.append((time.perf_counter() - start) * 1000)
            ordered = sorted(samples)
            return {
                "iterations": iterations,
                "median_ms": statistics.median(samples),
                "p95_ms": ordered[max(0, int(iterations * 0.95) - 1)],
                "max_ms": max(samples),
            }


if __name__ == "__main__":
    print(benchmark())
