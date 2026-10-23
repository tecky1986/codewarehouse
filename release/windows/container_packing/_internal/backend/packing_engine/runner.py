"""Algo scheduler: run multiple algorithms with time limit + progress."""

import time
from concurrent.futures import ThreadPoolExecutor

from packing_engine.kpi import evaluate
from packing_engine.model import Plan
from packing_engine.place import ALGORITHMS, ProgressReporter


def run_algorithms(
    items,
    containers_factory,
    algorithms: list[str],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    on_progress=None,
) -> tuple[list[Plan], dict[str, float]]:
    """Run each algorithm in a thread; returns (plans, elapsed_by_algo)."""
    time_limit = float(settings.get("time_limit_s", 60))
    elapsed_by_algo: dict[str, float] = {}
    plans: list[Plan] = []

    def one(name: str) -> Plan:
        rep = ProgressReporter(total=len(items), deadline_s=time_limit, on_progress=on_progress)
        t0 = time.monotonic()
        containers = containers_factory()
        fn = ALGORITHMS.get(name)
        if fn is None:
            plan = Plan(algorithm=name, containers=containers, unassigned=list(items))
            plan.elapsed_s = 0.0
            return plan
        plan = fn(items, containers, settings, enabled_rules, site_groups, rep)
        plan.elapsed_s = round(time.monotonic() - t0, 3)
        plan.kpi = evaluate(plan, len(items), elapsed_by_algo)
        return plan

    with ThreadPoolExecutor(max_workers=len(algorithms) or 1) as ex:
        futures = [ex.submit(one, name) for name in algorithms]
        for f in futures:
            plans.append(f.result())

    for p in plans:
        elapsed_by_algo[p.algorithm] = p.elapsed_s
        p.kpi = evaluate(p, len(items), elapsed_by_algo)
    return plans, elapsed_by_algo
