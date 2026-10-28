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
    freight = float(getattr(c, "freight_price", 0.0) or 0.0)

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
    # or per-step verify errors (E101–E112) attached by attach_verify.
    ok = 0
    for p in items:
        degraded = getattr(p, "degraded_rules", None)
        step_errors = getattr(p, "verify_errors", None)
        if not degraded and not step_errors:
            ok += 1

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
        "freight_price": freight,
        "inner_l": c.inner_l,
        "inner_w": c.inner_w,
        "inner_h": c.inner_h,
        "door_w": getattr(c, "door_w", None),
        "door_h": getattr(c, "door_h", None),
    }


def evaluate(plan: Plan, total_items: int, per_algo_elapsed: Optional[dict] = None) -> dict:
    used = [c for c in plan.containers if c.placed]
    per = [_per_container(c) for c in used]

    vol_used = sum(p["volume_used_m3"] for p in per)
    vol_cap = sum(p["volume_capacity_m3"] for p in per)
    gross_used = sum(p["payload_used_kg"] for p in per)
    gross_cap = sum(p["payload_capacity_kg"] for p in per)
    total_freight = sum(p.get("freight_price", 0.0) for p in per)

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
        "total_freight": total_freight,
        "elapsed_s": elapsed,
        "timed_out": bool(plan.timed_out),
    }

    return {"per_container": per, "overall": overall}


def attach_verify(plan: Plan, report) -> dict:
    """Merge a PlanReport into plan.kpi and per-placement verify_errors.

    Returns the updated kpi dict (also stored on plan.kpi).
    """
    by_label = {c.label: c for c in report.containers}
    for c in plan.containers:
        crep = by_label.get(c.label)
        if crep is None:
            continue
        err_by_uid: dict[str, list] = {}
        for s in crep.steps:
            if s.errors:
                err_by_uid.setdefault(s.uid, []).extend(list(s.errors))
        for p in c.placed:
            errs = err_by_uid.get(p.item.uid)
            if errs:
                p.verify_errors = errs

    kpi = plan.kpi or evaluate(plan, sum(len(c.placed) for c in plan.containers) + len(plan.unassigned or []))
    overall = kpi.setdefault("overall", {})
    overall["verify_ok"] = bool(report.ok)
    overall["verify_error_codes"] = dict(report.error_codes)
    overall["unload_ok"] = all(c.unload_ok for c in report.containers)
    per = kpi.get("per_container") or []
    per_by_label = {p["label"]: p for p in per}
    for c in report.containers:
        entry = per_by_label.get(c.label)
        if entry is None:
            continue
        n = entry.get("item_count") or 0
        bad = {s.uid for s in c.steps if s.errors}
        entry["constraint_ok_ratio"] = ((n - len(bad)) / n) if n else 1.0
        entry["verify_ok"] = c.ok
        entry["verify_error_codes"] = dict(c.error_codes)
        entry["unload_ok"] = c.unload_ok
    for c in plan.containers:
        entry = per_by_label.get(c.label)
        if entry is None:
            continue
        entry["inner_l"] = c.inner_l
        entry["inner_w"] = c.inner_w
        entry["inner_h"] = c.inner_h
        entry["door_w"] = getattr(c, "door_w", None)
        entry["door_h"] = getattr(c, "door_h", None)
    n_assigned = sum(p.get("item_count") or 0 for p in per)
    if n_assigned > 0:
        overall["constraint_ok_ratio"] = sum(
            p.get("constraint_ok_ratio", 1.0) * (p.get("item_count") or 0) for p in per
        ) / n_assigned
    else:
        overall["constraint_ok_ratio"] = 1.0
    plan.kpi = kpi
    return kpi


__all__ = ["evaluate", "attach_verify"]
_dataclass = dataclass  # noqa
