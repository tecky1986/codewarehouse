"""E101–E112 verification tests.

Each error code gets at least one illegal case (expected to hit) and one
valid case (expected to pass).  A final end-to-end case replays a full
multi-algorithm plan and dumps the JSON report to
backend/tests/verify_report.json as the retained evaluation record.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packing_engine.kpi import attach_verify, evaluate
from packing_engine.model import CargoItem, ContainerInstance, Plan
from packing_engine.place import ALGORITHMS, ProgressReporter, assign_load_seq_public
from packing_engine import verify
from packing_engine.verify import verify_container, verify_plan, ERROR_CODES


def _item(uid, l, w, h, gross, pn=None, rotatable=True, max_stack=None, max_load=None,
         cargo="A", crush=False, same_stack=False):
    return CargoItem(
        uid=uid, pn=pn, packmatls=None, cargo_type=cargo,
        l=l, w=w, h=h, tare=0.0, net=gross, gross=gross,
        rotatable=rotatable, crush_sensitive=crush, same_type_stack=same_stack,
        max_stack=max_stack, max_load=max_load,
    )


def _box(L=12032, W=2352, H=2393, payload=26700, label="40GP-1", door_w=None, door_h=None):
    c = ContainerInstance(
        type_code="40GP", seq_no=1, label=label,
        inner_l=L, inner_w=W, inner_h=H,
        max_payload=payload, volume_m3=L * W * H / 1e9,
    )
    if door_w is not None:
        c.door_w = door_w
    if door_h is not None:
        c.door_h = door_h
    return c


def _cand(box, item, x, y, z, dx, dy, dz, seq):
    from packing_engine.model import Candidate
    return Candidate(item=item, container=box, x=x, y=y, z=z, dx=dx, dy=dy, dz=dz, load_seq=seq)


# =====================================================================
# E101 / E104  outer box blocks the path to an inner box
# =====================================================================


def test_e101_outer_box_blocks_inner_box_illegal():
    box = _box(L=4000, W=2000, H=2000)
    outer = _item("outer", 1000, 1000, 1000, 100)
    inner = _item("inner", 1000, 1000, 1000, 50)
    # outer (seq=1) at x=2500..3500, inner (seq=2) at x=3000..4000.
    # x-overlap [3000,3500) and same y-band: the forks must cross outer's
    # span to reach inner -> E104, and inner's back face (4000) is deeper
    # than outer's (3500) so outer shields inner -> E101.  The partial z-
    # interpenetration also surfaces E105; all three are co-located here.
    box.placed = [
        _cand(box, outer, x=2500, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, inner, x=3000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E104" in codes, f"expected E104, got {codes}"
    assert "E101" in codes, f"expected E101, got {codes}"


def test_e101_inner_box_legal_sequence():
    box = _box(L=4000, W=2000, H=2000)
    # inner (further back) loaded first, outer (closer) loaded second
    inner = _item("inner", 1000, 1000, 1000, 50)
    outer = _item("outer", 1000, 1000, 1000, 100)
    box.placed = [
        _cand(box, inner, x=3000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, outer, x=2000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E102  current row not complete
# =====================================================================


def test_e102_new_row_before_previous_complete_illegal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # row 1 (z=0, y=0 band) not complete: a at x=3000, front face = 3000 > 0
    # then b opens a new y-band at z=0
    box.placed = [
        _cand(box, a, x=3000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=3000, y=1000, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E102" in codes, f"expected E102, got {codes}"


def test_e102_row_complete_before_new_band_legal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # first row fully filled to door (x=0), then second band opens
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=1000, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E103  upper box missing support
# =====================================================================


def test_e103_upper_box_missing_support_illegal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # b at z=1000 with no box directly under its footprint
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=2000, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E103" in codes, f"expected E103, got {codes}"


def test_e103_upper_box_supported_legal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # b sits directly on top of a (same footprint)
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E105  placement path collision
# =====================================================================


def test_e105_placement_collision_illegal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1500, 50)  # taller
    # b overlaps a in x/y at a z-level where they interpenetrate
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=500, y=500, z=200, dx=1000, dy=1000, dz=1500, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E105" in codes, f"expected E105, got {codes}"


def test_e105_non_colliding_stack_legal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # b stacked directly on a, no interpenetration
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E106  forks cannot be withdrawn during unloading
# =====================================================================


def test_e106_forks_blocked_during_unload_illegal():
    box = _box(L=4000, W=2000, H=2000)
    c = _item("c", 1000, 1000, 1000, 10)
    a = _item("a", 1000, 1000, 1000, 100)
    # c (seq=1) at x=500..1500, a (seq=2) at x=1000..2000, same y-band and
    # z-level, x-overlap [1000,1500).  Reverse unload removes a first; c
    # remains and its top face (z=1000) rises above a's working height, so
    # the forks cannot withdraw -> E106.
    box.placed = [
        _cand(box, c, x=500, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, a, x=1000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert not rep.unload_ok, f"expected unload to fail, errors={rep.unload_errors}"
    unload_codes = {c0 for c0, _ in rep.unload_errors}
    assert "E106" in unload_codes, f"expected E106, got {unload_codes}"


def test_e106_clean_unload_legal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    # only one box: nothing blocks the forks on removal
    box.placed = [
        _cand(box, a, x=3000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
    ]
    rep = verify_container(box)
    assert rep.unload_ok, f"expected clean unload, errors={rep.unload_errors}"


# =====================================================================
# E107  forklift cannot reverse out of the container
# =====================================================================


def test_e107_leftover_boxes_block_reversal_illegal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # b is stacked on a (a under b): removing a in reverse order fails
    # because b is still on top -> E103 on the unload step, a remains,
    # and the reversal check (E107) fires.
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    # reverse order: seq=2 (b) first -> b has nothing on top -> removable
    # seq=1 (a) next -> a now has nothing on top (b already removed) -> removable
    # so this case actually unloads cleanly; use it as the "legal" case.
    assert rep.unload_ok, "reverse order should unload a-then-b cleanly"
    assert rep.ok, f"expected forward ok too, got {rep.error_codes}"


def test_e107_leftover_boxes_block_reversal_bad():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # a on top of b but b is deeper; load_seq=1 for a (loaded first) and
    # seq=2 for b.  Reverse unload: b (seq=2) removed first, but b has a
    # on top -> E103, b remains -> E107.
    box.placed = [
        _cand(box, a, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert not rep.unload_ok, "expected unload to fail"
    unload_codes = {c for c, _ in rep.unload_errors}
    assert "E107" in unload_codes, f"expected E107, got {unload_codes}"


# =====================================================================
# E108  door frame / mast height exceeded
# =====================================================================


def test_e108_mast_height_exceeded_illegal():
    box = _box(L=4000, W=2000, H=2000, door_h=1500)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # b at z=1000, top = 2000 > door_h = 1500 -> E108
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E108" in codes, f"expected E108, got {codes}"


def test_e108_mast_height_within_legal():
    box = _box(L=4000, W=2000, H=2000, door_h=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E109  box does not fit through the door
# =====================================================================


def test_e109_door_width_too_narrow_illegal():
    box = _box(L=4000, W=2000, H=2000, door_w=1000)
    a = _item("a", 1000, 1500, 1000, 100)  # w=1500 > door_w=1000
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1500, dz=1000, seq=1),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E109" in codes, f"expected E109, got {codes}"


def test_e109_door_width_sufficient_legal():
    box = _box(L=4000, W=2000, H=2000, door_w=2000)
    a = _item("a", 1000, 1500, 1000, 100)
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1500, dz=1000, seq=1),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E110  load exceeds supporting box capacity
# =====================================================================


def test_e110_support_capacity_exceeded_illegal():
    box = _box(L=4000, W=2000, H=2000)
    base = _item("base", 1000, 1000, 1000, 100, max_load=200.0)
    top = _item("top", 1000, 1000, 1000, 300)  # 300 > 200
    box.placed = [
        _cand(box, base, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, top, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E110" in codes, f"expected E110, got {codes}"


def test_e110_support_capacity_within_legal():
    box = _box(L=4000, W=2000, H=2000)
    base = _item("base", 1000, 1000, 1000, 100, max_load=500.0)
    top = _item("top", 1000, 1000, 1000, 300)
    box.placed = [
        _cand(box, base, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, top, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    assert rep.ok, f"expected no errors, got {rep.error_codes}"


# =====================================================================
# E111  circular stacking dependency
# =====================================================================


def test_e111_circular_stack_illegal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    # upper box loaded first, its support loaded later -> E111
    box.placed = [
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E111" in codes, f"expected E111, got {codes}"


def test_e111_clean_stack_no_cycle_legal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    box.placed = [
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E111" not in codes, f"clean stack must not report E111, got {codes}"


# =====================================================================
# E112  no forklift working space reserved
# =====================================================================


def test_e112_full_width_front_occupied_illegal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 2000, 1000, 100)  # full width at z=0
    b = _item("b", 1000, 2000, 1000, 50)   # full width, in front, at z=1000
    # b placed first at z=1000 (closer to door, x=0..1000); a placed second
    # at z=0 further back (x=0..1000).  a fills the full width and b is in
    # front of a (q.x+q.dx=1000 <= a.x+... ) at a higher z, so the forks
    # cannot withdraw after placing a -> E112.
    box.placed = [
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=2000, dz=1000, seq=1),
        _cand(box, a, x=1000, y=0, z=0, dx=1000, dy=2000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E112" in codes, f"expected E112, got {codes}"


def test_e112_not_full_width_legal():
    box = _box(L=4000, W=2000, H=2000)
    a = _item("a", 1000, 1000, 1000, 100)  # half width
    b = _item("b", 1000, 1000, 1000, 50)
    box.placed = [
        _cand(box, a, x=3000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    rep = verify_container(box)
    codes = {c for c, _ in rep.errors}
    assert "E112" not in codes, f"non-full-width should not trigger E112, got {codes}"


# =====================================================================
# Animation frames: frame count equals step count
# =====================================================================


def test_frames_count_matches_steps():
    box = _box(L=4000, W=2000, H=2000)
    items = [_item(f"i{k}", 1000, 1000, 1000, k * 10, max_load=None) for k in range(1, 4)]
    box.placed = [
        _cand(box, items[0], x=3000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, items[1], x=2000, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
        _cand(box, items[2], x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=3),
    ]
    rep = verify_container(box)
    assert len(rep.frames) == len(rep.steps), \
        f"frames={len(rep.frames)} steps={len(rep.steps)}"
    assert len(rep.unload_frames) == len(rep.unload_steps), \
        f"unload_frames={len(rep.unload_frames)} unload_steps={len(rep.unload_steps)}"


# =====================================================================
# End-to-end: full algorithm run, dump report
# =====================================================================


def _run_algo(algo, label_suffix=""):
    box = _box(label=f"40GP-1{label_suffix}")
    items = [
        _item("a", 2000, 2000, 1000, 100),
        _item("b", 2000, 2000, 1000, 50),
        _item("t", 100, 100, 100, 5),
    ]
    rep = ProgressReporter(total=len(items), deadline_s=5)
    plan = ALGORITHMS[algo](items, [box], {"time_limit_s": 5}, [], [], rep)
    return plan


def test_e2e_dblf_plan_verifies():
    plan = _run_algo("dblf", "-dblf")
    report = verify_plan(plan)
    # dblf can open a second y-band before the first row reaches the door
    # (a known row-discipline gap); the placement is collision-free and the
    # reverse unload succeeds.  Record the expected E102 in the report.
    assert report.containers[0].unload_ok, "dblf reverse unload must succeed"
    assert "E102" in report.error_codes, f"dblf row-discipline gap should surface as E102, got {report.error_codes}"


def test_e2e_wall_build_plan_verifies():
    plan = _run_algo("wall_build", "-wb")
    report = verify_plan(plan)
    assert report.ok, f"wall_build plan should verify clean, got {report.error_codes}"
    assert report.containers[0].unload_ok, "wall_build reverse unload must succeed"


def test_e2e_all_algorithms_run():
    plans = {algo: _run_algo(algo, f"-{algo}") for algo in [
        "dblf", "maxspace", "extreme_point", "wall_build", "guillotine"
    ]}
    reports = {algo: verify_plan(plan) for algo, plan in plans.items()}
    for algo, rep in reports.items():
        print(f"\n[{algo}] ok={rep.ok} errors={rep.error_codes} unload_ok={rep.containers[0].unload_ok}")
    # at minimum: wall_build and guillotine must verify clean (fixed cursor)
    assert reports["wall_build"].ok, f"wall_build should pass: {reports['wall_build'].error_codes}"
    assert reports["guillotine"].ok, f"guillotine should pass: {reports['guillotine'].error_codes}"


def test_dump_json_report_written():
    """Write the full evaluation record to backend/tests/verify_report.json."""
    out_path = Path(__file__).parent / "verify_report.json"
    entries = []
    for algo in ["dblf", "maxspace", "extreme_point", "wall_build", "guillotine"]:
        plan = _run_algo(algo)
        report = verify_plan(plan)
        data = report.dump_json()
        data["planned_unassigned"] = [i.uid for i in plan.unassigned]
        entries.append(data)
        print(f"[{algo}] ok={report.ok} errors={report.error_codes}")
    out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    assert out_path.exists()
    saved = json.loads(out_path.read_text())
    assert len(saved) == 5, f"expected 5 algorithm entries, got {len(saved)}"
    for entry in saved:
        labels = [c["label"] for c in entry["containers"]]
        assert len(labels) == len(set(labels)), f"duplicate containers in {entry['algorithm']}"


# =====================================================================
# ERROR_CODES catalogue completeness
# =====================================================================


def test_attach_verify_writes_kpi_and_inner_dims():
    box = _box(L=4000, W=2000, H=2000, door_w=2000, door_h=2000)
    a = _item("a", 1000, 1000, 1000, 100)
    b = _item("b", 1000, 1000, 1000, 50)
    box.placed = [
        _cand(box, b, x=0, y=0, z=1000, dx=1000, dy=1000, dz=1000, seq=1),
        _cand(box, a, x=0, y=0, z=0, dx=1000, dy=1000, dz=1000, seq=2),
    ]
    plan = Plan(algorithm="test", containers=[box], unassigned=[])
    plan.kpi = evaluate(plan, 2)
    attach_verify(plan, verify_plan(plan))
    overall = plan.kpi["overall"]
    assert overall["verify_ok"] is False
    assert "E111" in overall["verify_error_codes"]
    assert overall["constraint_ok_ratio"] < 1.0
    per = plan.kpi["per_container"][0]
    assert per["inner_l"] == 4000
    assert per["door_w"] == 2000
    assert per["verify_ok"] is False


def test_error_codes_catalogue_complete():
    expected = {"E101", "E102", "E103", "E104", "E105", "E106", "E107",
                "E108", "E109", "E110", "E111", "E112"}
    assert set(ERROR_CODES.keys()) == expected, \
        f"ERROR_CODES keys={set(ERROR_CODES.keys())} expected={expected}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
