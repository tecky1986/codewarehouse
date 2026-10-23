import time

import pytest

from packing_engine import ALGORITHMS
from packing_engine.model import CargoItem, ContainerInstance
from packing_engine.place import ProgressReporter
from packing_engine.kpi import evaluate
from packing_engine.rules import CheckContext, run_checkers
from packing_engine import Candidate


def _item(uid, l, w, h, gross, pn=None, crush=False, same_stack=False, loading="manual", cargo="A", rotatable=True):
    return CargoItem(
        uid=uid,
        pn=pn,
        packmatls=None,
        cargo_type=cargo,
        l=l,
        w=w,
        h=h,
        gross=gross,
        net=gross,
        rotatable=rotatable,
        crush_sensitive=crush,
        same_type_stack=same_stack,
        loading=loading,
    )


def _box(L=12032, W=2352, H=2393, payload=26700):
    return ContainerInstance(
        type_code="40GP",
        seq_no=1,
        label="40GP-1",
        inner_l=L,
        inner_w=W,
        inner_h=H,
        max_payload=payload,
        volume_m3=L * W * H / 1e9,
    )


def test_dblf_fills_in_order():
    box = _box()
    items = [
        _item("a", 1000, 500, 500, 100),
        _item("b", 1000, 500, 500, 50),
    ]
    rep = ProgressReporter(total=2, deadline_s=5)
    plan = ALGORITHMS["dblf"](items, [box], {"time_limit_s": 5}, [], [], rep)
    assert not plan.unassigned
    assert len(box.placed) == 2
    assert box.placed[0].load_seq == 1
    assert box.placed[1].load_seq == 2
    # no AABB overlap
    p, q = box.placed
    assert not (
        p.x < q.x + q.dx and q.x < p.x + p.dx
        and p.y < q.y + q.dy and q.y < p.y + p.dy
        and p.z < q.z + q.dz and q.z < p.z + p.dz
    )


def test_pn_continuity_split_across_containers():
    c1 = _box(L=3000, W=1000, H=1000, payload=1000)
    c1.label = "40GP-1"
    c2 = _box(L=3000, W=1000, H=1000, payload=1000)
    c2.label = "40GP-2"
    c2.seq_no = 2
    items = [
        _item(f"p{i}", 1000, 1000, 1000, 50, pn="P1", rotatable=False) for i in range(4)
    ]
    rep = ProgressReporter(total=len(items), deadline_s=5)
    plan = ALGORITHMS["dblf"](items, [c1, c2], {"time_limit_s": 5}, ["pn_continuous"], [], rep)
    in_c1 = [p for p in c1.placed]
    in_c2 = [p for p in c2.placed]
    assert len(in_c1) + len(in_c2) == 4
    # c1 holds 3 (row of 3), c2 continues with 1 -> R8.2 chain split
    assert len(in_c1) == 3 and len(in_c2) == 1
    for group in (in_c1, in_c2):
        if not group:
            continue
        intervals = sorted((p.x, p.x + p.dx) for p in group)
        lo, hi = intervals[0]
        for a, b in intervals[1:]:
            assert a <= hi + 1e-6, f"gap in PN x intervals: {intervals}"
            hi = max(hi, b)
        assert abs((hi - lo) - sum(p.dx for p in group)) < 1e-6


def test_payload_rule():
    box = _box(payload=100)
    it = _item("p", 100, 100, 100, 120)
    cand = Candidate(item=it, container=box, x=0, y=0, z=0, dx=100, dy=100, dz=100, load_seq=1)
    v = run_checkers(cand, CheckContext(settings={}, placed=[]), ["payload"])
    assert ("payload", "超过最大载重") in v


def test_inside_out_rule():
    box = _box(L=4000)
    deep = _item("d", 2000, 1000, 1000, 100)
    shallow = _item("s", 2000, 1000, 1000, 100)
    c1 = Candidate(item=deep, container=box, x=2000, y=0, z=0, dx=2000, dy=1000, dz=1000, load_seq=1)
    # deep face = 4000
    v1 = run_checkers(c1, CheckContext(settings={}, placed=[]), ["inside_out"])
    assert v1 == []
    c2 = Candidate(item=shallow, container=box, x=2000, y=1000, z=0, dx=2000, dy=1000, dz=1000, load_seq=2)
    # shallower item placed later with same deep face 4000, must be <= earlier min face 4000 -> ok
    assert run_checkers(c2, CheckContext(settings={}, placed=[c1]), ["inside_out"]) == []
    # now an item extending deeper than earlier item: violation
    c3 = Candidate(item=shallow, container=box, x=2500, y=1000, z=0, dx=2000, dy=1000, dz=1000, load_seq=3)
    v3 = run_checkers(c3, CheckContext(settings={}, placed=[c1]), ["inside_out"])
    assert ("inside_out", "由内向外顺序不满足") in v3


def test_kpi_overall_recomputable_from_per_container():
    c1 = _box()
    c2 = _box()
    c2.label = "40GP-2"
    c2.seq_no = 2
    from packing_engine import Plan

    box_items = [_item(f"a{i}", 1000, 1000, 1000, 100) for i in range(2)]
    for i, it in enumerate(box_items):
        # seq 1 is the deepest item (x=1000), seq 2 in front (x=0)
        c1.placed.append(Candidate(item=it, container=c1, x=(1 - i) * 1000, y=0, z=0, dx=1000, dy=1000, dz=1000, load_seq=i + 1))
    box_items2 = [_item(f"b{i}", 1000, 1000, 1000, 100) for i in range(2)]
    for i, it in enumerate(box_items2):
        c2.placed.append(Candidate(item=it, container=c2, x=(1 - i) * 1000, y=0, z=0, dx=1000, dy=1000, dz=1000, load_seq=i + 1))
    unassigned = [_item("u1", 1000, 1000, 1000, 100)]
    plan = Plan(algorithm="dblf", containers=[c1, c2], unassigned=unassigned)
    kpi = evaluate(plan, total_items=5, per_algo_elapsed={"dblf": 0.5})

    per = kpi["per_container"]
    overall = kpi["overall"]
    assert len(per) == 2
    # R30: overall vol/util recompute from per-container
    vol_used = sum(p["volume_used_m3"] for p in per)
    vol_cap = sum(p["volume_capacity_m3"] for p in per)
    assert abs(overall["vol_util"] - vol_used / vol_cap) < 1e-6
    gross_used = sum(p["payload_used_kg"] for p in per)
    gross_cap = sum(p["payload_capacity_kg"] for p in per)
    assert abs(overall["pay_util"] - gross_used / gross_cap) < 1e-6
    assert overall["containers_used"] == 2
    assert overall["completion"] == 0.8  # 4/5
    assert overall["unassigned_count"] == 1
    assert overall["unassigned_weight_kg"] == 100.0
    # weighted
    assert overall["load_seq_correct_ratio"] == 1.0
    assert overall["constraint_ok_ratio"] == 1.0


def test_dblf_unassigned_when_no_space():
    box = _box(L=1000, W=1000, H=1000, payload=10000)
    items = [
        _item("a", 1000, 1000, 1000, 100),
        _item("b", 1000, 1000, 1000, 100),
    ]
    rep = ProgressReporter(total=2, deadline_s=5)
    plan = ALGORITHMS["dblf"](items, [box], {"time_limit_s": 5}, [], [], rep)
    assert len(box.placed) == 1
    assert len(plan.unassigned) == 1
    assert plan.unassigned[0].uid == "b"


def test_timeout_marks_partial_plan():
    box = _box()
    items = [_item(f"i{i}", 500, 500, 500, 10) for i in range(50)]
    rep = ProgressReporter(total=len(items), deadline_s=0.000001)  # immediate
    plan = ALGORITHMS["dblf"](items, [box], {"time_limit_s": 0.000001}, [], [], rep)
    assert plan.timed_out is True
    assert 0 < len(box.placed) < len(items) or len(box.placed) + len(plan.unassigned) == len(items)
