import time

import pytest

from packing_engine import ALGORITHMS
from packing_engine.model import CargoItem, ContainerInstance
from packing_engine.place import ProgressReporter
from packing_engine.kpi import evaluate
from packing_engine.rules import CheckContext, run_checkers
from packing_engine import Candidate


def _item(uid, l, w, h, gross, pn=None, same_stack=False, loading="manual", cargo="A", rotatable=True, max_load=0.0):
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
        same_type_stack=same_stack,
        loading=loading,
        max_load=max_load,
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


def test_stack_support_uses_one_or_two_equal_rows():
    box = _box(L=1000, W=2000, H=2000, payload=100000)
    base_a = _item("a", 1000, 1000, 500, 100, rotatable=False)
    base_b = _item("b", 1000, 1000, 500, 100, rotatable=False)
    top = _item("top", 1000, 2000, 400, 100, rotatable=False)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=base_a, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
        Candidate(item=base_b, container=box, x=0, y=1000, z=0, dx=1000, dy=1000, dz=500, load_seq=2),
    ])
    cand = Candidate(item=top, container=box, x=0, y=0, z=500, dx=1000, dy=2000, dz=400, load_seq=3)
    assert run_checkers(cand, ctx, ["stack_support"]) == []


def test_stack_support_rejects_unequal_support_heights():
    box = _box(L=1000, W=2000, H=2000, payload=100000)
    base_a = _item("a", 1000, 1000, 500, 100, rotatable=False)
    base_b = _item("b", 1000, 1000, 400, 100, rotatable=False)
    top = _item("top", 1000, 2000, 400, 100, rotatable=False)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=base_a, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
        Candidate(item=base_b, container=box, x=0, y=1000, z=100, dx=1000, dy=1000, dz=400, load_seq=2),
    ])
    cand = Candidate(item=top, container=box, x=0, y=0, z=500, dx=1000, dy=2000, dz=400, load_seq=3)
    assert ("stack_support", "被压货物高度不一致") in run_checkers(cand, ctx, ["stack_support"])


def test_load_seq_starts_from_innermost_lowest_width_side():
    box = _box(L=3000, W=2000, H=2000, payload=100000)
    from packing_engine.place import assign_load_seq_public as assign_load_seq

    box.placed.append(Candidate(item=_item("inner", 1000, 1000, 1000, 100, rotatable=False), container=box, x=2000, y=0, z=0, dx=1000, dy=1000, dz=1000, load_seq=99))
    box.placed.append(Candidate(item=_item("top", 1000, 1000, 500, 100, rotatable=False), container=box, x=2000, y=0, z=1000, dx=1000, dy=1000, dz=500, load_seq=98))
    box.placed.append(Candidate(item=_item("side", 1000, 1000, 1000, 100, rotatable=False), container=box, x=2000, y=1000, z=0, dx=1000, dy=1000, dz=1000, load_seq=97))
    box.placed.append(Candidate(item=_item("door", 1000, 1000, 1000, 100, rotatable=False), container=box, x=1000, y=0, z=0, dx=1000, dy=1000, dz=1000, load_seq=96))

    assign_load_seq([box])
    seq = {p.item.uid: p.load_seq for p in box.placed}
    assert seq["inner"] == 1
    assert seq["side"] == 2
    assert seq["door"] == 3
    assert seq["top"] == 4


def test_dblf_fills_width_row_before_top():
    box = _box(L=1000, W=2000, H=2000, payload=100000)
    items = [
        _item("a", 1000, 1000, 1000, 100, rotatable=False),
        _item("b", 1000, 1000, 1000, 100, rotatable=False),
        _item("top", 1000, 2000, 500, 100, rotatable=False),
    ]
    rep = ProgressReporter(total=len(items), deadline_s=5)
    plan = ALGORITHMS["dblf"](items, [box], {"time_limit_s": 5}, [], [], rep)
    assert not plan.unassigned
    seq = {p.item.uid: p.load_seq for p in box.placed}
    assert seq["a"] == 1
    assert seq["b"] == 2
    assert seq["top"] == 3
    by_uid = {p.item.uid: p for p in box.placed}
    assert by_uid["top"].z == 1000
    assert by_uid["top"].dy == 2000


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


def test_wall_build_fills_width_row_before_top():
    box = _box(L=1000, W=2000, H=2000, payload=100000)
    items = [
        _item("a", 1000, 1000, 1000, 100, rotatable=False),
        _item("b", 1000, 1000, 1000, 100, rotatable=False),
        _item("top", 1000, 2000, 500, 100, rotatable=False),
    ]
    rep = ProgressReporter(total=len(items), deadline_s=5)
    plan = ALGORITHMS["wall_build"](items, [box], {"time_limit_s": 5}, [], [], rep)
    assert not plan.unassigned
    seq = {p.item.uid: p.load_seq for p in box.placed}
    assert seq["a"] == 1
    assert seq["b"] == 2
    assert seq["top"] == 3
    by_uid = {p.item.uid: p for p in box.placed}
    assert by_uid["top"].z == 1000
    assert by_uid["top"].dy == 2000


def test_wall_fill_dense_floors():
    box = ContainerInstance(
        type_code="40GP",
        seq_no=1,
        label="40GP-1",
        inner_l=12192,
        inner_w=2352,
        inner_h=2280,
        max_payload=26000,
        volume_m3=12192 * 2352 * 2280 / 1e9,
    )
    items = [
        _item("A1", 1460, 1150, 1100, 400, cargo="A", rotatable=False),
        _item("A2", 1460, 1150, 1100, 300, cargo="A", rotatable=False),
        _item("B1", 770, 770, 850, 60, cargo="B", rotatable=False),
        _item("B2", 770, 770, 850, 50, cargo="B", rotatable=False),
    ]
    rep = ProgressReporter(total=len(items), deadline_s=5)
    plan = ALGORITHMS["wall_fill"](items, [box], {"time_limit_s": 5}, [], [], rep)
    assert plan.unassigned == []
    assert len(box.placed) == 4
    by_uid = {p.item.uid: p for p in box.placed}
    assert by_uid["A1"].z == 0, f"first type-A item must sit on the floor, got z={by_uid['A1'].z}"
    assert by_uid["A2"].z == 0, f"second type-A item must sit on the floor, got z={by_uid['A2'].z}"


def test_timeout_marks_partial_plan():
    box = _box()
    items = [_item(f"i{i}", 500, 500, 500, 10) for i in range(50)]
    rep = ProgressReporter(total=len(items), deadline_s=0.000001)  # immediate
    plan = ALGORITHMS["dblf"](items, [box], {"time_limit_s": 0.000001}, [], [], rep)
    assert plan.timed_out is True
    assert 0 < len(box.placed) < len(items) or len(box.placed) + len(plan.unassigned) == len(items)


# ---- max_stack_layers rule --------------------------------------------

def test_max_stack_layers_rule_item_limit():
    box = _box()
    it1 = CargoItem(uid="b", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                    gross=10, net=10, max_stack=2, rotatable=False, same_type_stack=True)
    it2 = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                    gross=10, net=10, max_stack=2, rotatable=False, same_type_stack=True)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=it1, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
        Candidate(item=CargoItem(uid="b2", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                                  gross=10, net=10, max_stack=2, rotatable=False, same_type_stack=True),
                  container=box, x=0, y=0, z=500, dx=1000, dy=1000, dz=500, load_seq=2),
    ])
    cand = Candidate(item=it2, container=box, x=0, y=0, z=1000, dx=1000, dy=1000, dz=500, load_seq=3)
    v = run_checkers(cand, ctx, ["max_stack_layers"])
    assert ("max_stack_layers", "超过最大堆码层数（上限 2 层）") in v


def test_max_stack_layers_rule_container_limit():
    box = _box()
    # container-level max_stack_layers removed; the limit now comes from the
    # candidate item's own max_stack. The candidate here has max_stack=2,
    # and is being placed at z=1000 (3rd layer), so it violates the limit.
    it = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                   gross=10, net=10, rotatable=False, max_stack=2, same_type_stack=True)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=CargoItem(uid="b", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                                  gross=10, net=10, rotatable=False, max_stack=2, same_type_stack=True),
                   container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
        Candidate(item=CargoItem(uid="b2", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                                  gross=10, net=10, rotatable=False, max_stack=2, same_type_stack=True),
                   container=box, x=0, y=0, z=500, dx=1000, dy=1000, dz=500, load_seq=2),
    ])
    cand = Candidate(item=it, container=box, x=0, y=0, z=1000, dx=1000, dy=1000, dz=500, load_seq=3)
    v = run_checkers(cand, ctx, ["max_stack_layers"])
    assert ("max_stack_layers", "超过最大堆码层数（上限 2 层）") in v


# ---- max_load rule -----------------------------------------------------

def test_max_load_exceeds_capacity():
    box = _box()
    base = CargoItem(uid="b", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                     gross=10, net=10, rotatable=False, max_load=100)
    top = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                    gross=200, net=200, rotatable=False)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=base, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
    ])
    cand = Candidate(item=top, container=box, x=0, y=0, z=500, dx=1000, dy=1000, dz=500, load_seq=2)
    v = run_checkers(cand, ctx, ["max_stack_layers"])
    assert ("max_stack_layers", "被压货物承重超限（100 kg）") in v


def test_max_load_half_weight_cross_box():
    box = _box()
    # two supports side-by-side, one is a cross-box split (straddling)
    base1 = CargoItem(uid="b1", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                      gross=10, net=10, rotatable=False, max_load=100)
    base2 = CargoItem(uid="b2", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                      gross=10, net=10, rotatable=False, max_load=100)
    # top straddles both base items -> each gets half the top weight
    top = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=2000, w=1000, h=500,
                    gross=250, net=250, rotatable=False)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=base1, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
        Candidate(item=base2, container=box, x=1000, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=2),
    ])
    cand = Candidate(item=top, container=box, x=0, y=0, z=500, dx=2000, dy=1000, dz=500, load_seq=3)
    # half-weight: 125 kg on each base, exceeds 100 kg capacity -> violation
    v = run_checkers(cand, ctx, ["max_stack_layers"])
    assert ("max_stack_layers", "被压货物承重超限（100 kg）") in v


def test_max_load_half_weight_cross_box_within_limit():
    box = _box()
    base1 = CargoItem(uid="b1", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                      gross=10, net=10, rotatable=False, max_load=100)
    base2 = CargoItem(uid="b2", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                      gross=10, net=10, rotatable=False, max_load=100)
    top = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=2000, w=1000, h=500,
                    gross=100, net=100, rotatable=False)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=base1, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
        Candidate(item=base2, container=box, x=1000, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=2),
    ])
    cand = Candidate(item=top, container=box, x=0, y=0, z=500, dx=2000, dy=1000, dz=500, load_seq=3)
    # half-weight: 50 kg on each base, 50 <= 100 -> no violation
    v = run_checkers(cand, ctx, ["max_stack_layers"])
    assert ("max_stack_layers", "被压货物承重超限") not in v


def test_max_load_none_unlimited():
    box = _box()
    base = CargoItem(uid="b", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                     gross=10, net=10, rotatable=False)  # max_load=None
    top = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                    gross=9999, net=9999, rotatable=False)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=base, container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
    ])
    cand = Candidate(item=top, container=box, x=0, y=0, z=500, dx=1000, dy=1000, dz=500, load_seq=2)
    assert run_checkers(cand, ctx, ["max_stack_layers"]) == []


def test_max_stack_layers_no_violation_within_limit():
    box = _box()
    it = CargoItem(uid="t", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                   gross=10, net=10, rotatable=False, max_stack=3)
    ctx = CheckContext(settings={}, placed=[
        Candidate(item=CargoItem(uid="b", pn=None, packmatls=None, cargo_type="A", l=1000, w=1000, h=500,
                                  gross=10, net=10, rotatable=False, max_stack=3),
                   container=box, x=0, y=0, z=0, dx=1000, dy=1000, dz=500, load_seq=1),
    ])
    cand = Candidate(item=it, container=box, x=0, y=0, z=500, dx=1000, dy=1000, dz=500, load_seq=2)
    assert run_checkers(cand, ctx, ["max_stack_layers"]) == []


# ---- PN wildcard matching in normalize ----------------------------------

def test_normalize_pn_wildcard_match():
    from packing_engine.normalize import items_from_rows, _match_pn

    # ? matches any number of any chars
    assert _match_pn("ACW1081", "ACW?")
    assert _match_pn("ACW1081490", "ACW?")
    assert _match_pn("ACW", "ACW?")
    assert not _match_pn("BACW", "ACW?")
    # # matches exactly one char per #
    assert _match_pn("AB1CD", "AB#CD")
    assert not _match_pn("ABCD", "AB#CD")
    assert _match_pn("AB12CD", "AB##CD")
    assert not _match_pn("AB1CD", "AB##CD")
    # no wildcard = exact only
    assert _match_pn("ACW1081", "ACW1081")
    assert not _match_pn("ACW10814", "ACW1081")
    # combined ? and #
    assert _match_pn("A12X345B", "A?#B")
    assert not _match_pn("A12X345C", "A?#B")

    # items_from_rows picks up rule attributes from wildcard master
    packages = [
        {"pn": "ACW?1", "name": "WILD", "rotatable": 0,
         "same_type_stack": 1, "max_stack": 3, "default_loading": "forklift"},
    ]
    rows = [{"id": 1, "row_no": 1, "k_pn": "ACW1081", "g_packmatls": None,
             "b_len": 1000, "c_wid": 500, "d_hgt": 300, "h_tare": 10, "i_net": 20,
             "j_gross": 30, "complete": True}]
    items = items_from_rows(rows, packages)
    assert len(items) == 1
    it = items[0]
    assert it.rotatable is False
    assert it.same_type_stack is True
    assert it.max_stack == 3
    assert it.loading == "forklift"
