"""KPI: per-container + overall formulas (single implementation, R30/P3).

All percent-ratios stored as fractions (0..1) and rendered as 0.0%–100.0%
with one decimal on the frontend.
"""

from dataclasses import dataclass, field
from typing import Optional

from packing_engine.geometry import EPS
from packing_engine.model import Plan


def _per_container(c, total_elapsed: float = 0.0) -> dict:
    items = c.placed
    n = len(items)
    vol_used = sum(p.item.volume_m3() for p in items)
    gross_used = sum(p.item.gross for p in items)

    # load-seq correctness: an item is "in order" when its inner face
    # (x+dx) does not exceed the minimum inner face of earlier items.
    # Stacked items (same inner face) stay in order.
    seq_ok = 0
    if n:
        placed_sorted = sorted(items, key=lambda p: p.load_seq)
        faces = [p.x + p.dx for p in placed_sorted]
        min_so_far: float | None = None
        for face in faces:
            if min_so_far is None or face <= min_so_far + EPS:
                seq_ok += 1
            min_so_far = face if min_so_far is None else min(min_so_far, face)

    # constraint satisfaction: share of placements without degraded rules
    ok = sum(1 for p in items if not getattr(p, "degraded_rules", None))

    # center of gravity offset along x
    if n and gross_used > 0:
        cg = sum(p.item.gross * (p.x + p.dx / 2.0) for p in items) / gross_used
        cg_offset = abs(cg - c.inner_l / 2.0)
    else:
        cg_offset = 0.0

    return {
        "label": c.label,
        "type_code": c.type_code,
        "item_count": n,
        "volume_used_m3": vol_used,
        "volume_capacity_m3": c.volume_m3,
        "vol_util": (vol_used / c.volume_m3) if c.volume_m3 > 0 else 0.0,
        "payload_used_kg": gross_used,
        "payload_capacity_kg": c.max_payload,
        "pay_util": (gross_used / c.max_payload) if c.max_payload > 0 else 0.0,
        "load_seq_correct_ratio": (seq_ok / n) if n else 1.0,
        "constraint_ok_ratio": (ok / n) if n else 1.0,
        "cg_offset_mm": cg_offset,
    }


def evaluate(plan: Plan, total_items: int, per_algo_elapsed: Optional[dict] = None) -> dict:
    used = [c for c in plan.containers if c.placed]
    per = [_per_container(c) for c in used]

    vol_used = sum(p["volume_used_m3"] for p in per)
    vol_cap = sum(p["volume_capacity_m3"] for p in per)
    gross_used = sum(p["payload_used_kg"] for p in per)
    gross_cap = sum(p["payload_capacity_kg"] for p in per)

    assigned = sum(p["item_count"] for p in per)
    unassigned_items = plan.unassigned or []
    un_vol = sum(i.volume_m3() for i in unassigned_items)
    un_gross = sum(i.gross for i in unassigned_items)

    n_assigned = max(assigned, 0)
    total = max(total_items, 0)

    seq_ratios = [p["load_seq_correct_ratio"] for p in per if p["item_count"]]
    ok_ratios = [p["constraint_ok_ratio"] for p in per if p["item_count"]]
    # weighted by item count
    if n_assigned > 0:
        weighted_seq = sum(
            p["load_seq_correct_ratio"] * p["item_count"] for p in per
        ) / n_assigned
        weighted_ok = sum(p["constraint_ok_ratio"] * p["item_count"] for p in per) / n_assigned
    else:
        weighted_seq = 1.0
        weighted_ok = 1.0

    elapsed = 0.0
    if per_algo_elapsed:
        elapsed = max(per_algo_elapsed.get(plan.algorithm, 0.0), 0.0)

    overall = {
        "vol_util": (vol_used / vol_cap) if vol_cap > 0 else 0.0,
        "pay_util": (gross_used / gross_cap) if gross_cap > 0 else 0.0,
        "containers_used": len(used),
        "completion": (assigned / total) if total else 1.0,
        "unassigned_count": len(unassigned_items),
        "unassigned_volume_m3": un_vol,
        "unassigned_weight_kg": un_gross,
        "load_seq_correct_ratio": weighted_seq,
        "constraint_ok_ratio": weighted_ok,
        "elapsed_s": elapsed,
        "timed_out": bool(plan.timed_out),
    }

    return {"per_container": per, "overall": overall}


__all__ = ["evaluate"]
_dataclass = dataclass  # noqa
