from itertools import product

from packing_engine.kpi import evaluate
from packing_engine.model import ContainerInstance, Plan
from packing_engine.place import ALGORITHMS, ProgressReporter, dblf


def _instances_for(types: list[tuple[str, int]], catalog: dict[str, ContainerInstance]) -> list[ContainerInstance]:
    out: list[ContainerInstance] = []
    counters: dict[str, int] = {}
    for code, n in types:
        proto = catalog[code]
        for _ in range(n):
            counters[code] = counters.get(code, 0) + 1
            out.append(
                ContainerInstance(
                    type_code=proto.type_code,
                    seq_no=counters[code],
                    label=f"{proto.type_code}-{counters[code]}",
                    inner_l=proto.inner_l,
                    inner_w=proto.inner_w,
                    inner_h=proto.inner_h,
                    max_payload=proto.max_payload,
                    volume_m3=proto.volume_m3,
                    freight_price=getattr(proto, "freight_price", 0.0),
                    door_w=getattr(proto, "door_w", None),
                    door_h=getattr(proto, "door_h", None),
                )
            )
    return out


def lower_bound(items, catalog: dict[str, ContainerInstance]) -> int:
    total_vol = sum(i.volume_m3() for i in items)
    total_gross = sum(i.gross for i in items)
    max_vol = max(c.volume_m3 for c in catalog.values()) if catalog else 0
    max_pay = max(c.max_payload for c in catalog.values()) if catalog else 0
    lb_vol = int(-(-total_vol // max_vol)) if max_vol > 0 else 0
    lb_pay = int(-(-total_gross // max_pay)) if max_pay > 0 else 0
    return max(lb_vol, lb_pay, 1) if items else 1


def combinations_bounded(
    catalog_codes: list[str],
    locks: dict,
    lower: int,
    upper: int,
    deadline_check=None,
):
    """Yield type-count combinations respecting type/quantity locks.

    locks: {"type_lock": [codes...], "qty_lock": {"40GP": 1, ...}, "max_qty": {"40GP": 3}}
    """
    type_lock = set(locks.get("type_lock") or catalog_codes)
    allowed = [c for c in catalog_codes if c in type_lock]
    qty_lock = locks.get("qty_lock") or {}
    max_qty = locks.get("max_qty") or {}
    if not allowed:
        return
    counts_limits = {
        c: (max_qty.get(c, upper), upper) for c in allowed
    }
    # fixed part from qty_lock
    fixed_total = 0
    fixed_counts: dict[str, int] = {}
    for c, n in qty_lock.items():
        if c in allowed:
            fixed_counts[c] = int(n)
            fixed_total += int(n)
    variable = [c for c in allowed if c not in fixed_counts]
    var_limits = [counts_limits[c][0] for c in variable]
    total_slots = upper - fixed_total
    if total_slots < 0:
        return

    def rec(i, remaining, acc):
        if i == len(variable):
            if remaining == 0:
                yield dict(acc)
            return
        lim = min(var_limits[i], remaining)
        for n in range(lim + 1):
            if i == len(variable) - 1:
                n = remaining  # last takes all
                if n <= var_limits[i]:
                    yield dict(acc, **{variable[i]: n})
                continue
            acc[variable[i]] = n
            yield from rec(i + 1, remaining - n, acc)

    for var_counts in rec(0, total_slots, {}):
        combo = {**fixed_counts, **{c: var_counts.get(c, 0) for c in variable}}
        combo_list = [(c, n) for c, n in combo.items() if n > 0]
        if deadline_check and deadline_check():
            return
        yield combo_list


def search(
    items: list,
    catalog: dict[str, ContainerInstance],
    locks: dict,
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> tuple[Plan | None, str | None, bool]:
    """Return (best_plan, error, timed_out).

    Optimization objective: minimize total freight cost among plans that
    place all items (completion == 1.0).  If no plan places everything,
    fall back to maximising completion, then minimising container count.
    """
    catalog_codes = list(catalog.keys())
    lb = lower_bound(items, catalog)
    upper = min(lb + 3, 20)

    combos = list(combinations_bounded(catalog_codes, locks, lb, upper))
    if not combos:
        return None, "E_NO_FEASIBLE", False

    best: tuple[tuple, Plan] | None = None
    for combo in combos:
        if reporter.timed_out:
            break
        containers = _instances_for(combo, catalog)
        sub_rep = ProgressReporter(
            total=len(items),
            deadline_s=reporter.remaining() if reporter.remaining() > 0 else float(settings.get("time_limit_s", 60)) / max(len(combos), 1),
        )
        plan = dblf(items, containers, settings, enabled_rules, site_groups, sub_rep)
        plan.kpi = evaluate(plan, len(items))
        overall = plan.kpi["overall"]
        completion = overall["completion"]
        used = overall["containers_used"]
        vol_util = overall["vol_util"]
        freight = overall.get("total_freight", 0.0)
        # Primary: fully loaded? Secondary: lowest freight. Tertiary: fewer containers, higher vol util.
        fully_loaded = 0 if completion >= 1.0 - 1e-9 else 1
        key = (fully_loaded, freight, used, -vol_util)
        if best is None or key < best[0]:
            best = (key, plan)
        reporter.tick()

    if best is None:
        return None, "E_NO_FEASIBLE", reporter.timed_out
    _, plan = best
    if plan.unassigned:
        return None, "E_NO_FEASIBLE", reporter.timed_out
    return plan, None, reporter.timed_out
