"""Additional placement strategies (cap-candidate model).

See place.py module docstring for coordinate conventions.  A candidate is
(cap, y, z): the item is placed flush with its back face at cap, i.e.
item.x = cap - dx.
"""

from packing_engine.groups import order_items
from packing_engine.model import Candidate, CargoItem, ContainerInstance, Plan
from packing_engine.place import ProgressReporter, _finish_plan, register
from packing_engine.rules import CheckContext, run_checkers


def _orientations(item: CargoItem):
    if item.rotatable:
        return [(item.l, item.w, item.h), (item.w, item.l, item.h)]
    return [(item.l, item.w, item.h)]


def _try_at_cap(
    cap: float,
    y: float,
    z: float,
    item: CargoItem,
    c: ContainerInstance,
    settings: dict,
    enabled_rules,
) -> Candidate | None:
    load_seq = len(c.placed) + 1
    check_ctx = CheckContext(settings=settings, placed=c.placed)
    for (dx, dy, dz) in _orientations(item):
        x0 = cap - dx
        if x0 < -1e-9:
            continue
        if dy > c.inner_w - y + 1e-9 or dz > c.inner_h - z + 1e-9:
            continue
        cand = Candidate(
            item=item,
            container=c,
            x=max(0.0, x0),
            y=y,
            z=z,
            dx=dx,
            dy=dy,
            dz=dz,
            load_seq=load_seq,
        )
        if not run_checkers(cand, check_ctx, enabled_rules):
            return cand
    return None


def _advance_cursor(cand: Candidate, c: ContainerInstance) -> tuple[float, float, float]:
    """Wall cursor after placing cand: fill width, then height, then new wall."""
    cap = cand.x
    y = cand.y + cand.dy
    z = cand.z
    if y >= c.inner_w - 1e-9:
        y = 0.0
        z = cand.z + cand.dz
    if z >= c.inner_h - 1e-9:
        cap = float(c.inner_l)
        z = 0.0
    return (cap, y, z)


# ---------------------------------------------------------------------------
# Extreme point heuristic.
# ---------------------------------------------------------------------------


def extreme_point(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    unassigned: list[CargoItem] = []
    for item in order_items(items):
        if reporter.timed_out:
            rest = [i for i in order_items(items) if i.uid == item.uid]
            unassigned.extend(rest)
            return _finish_plan("extreme_point", containers, unassigned, timed_out=True)
        placed = False
        for c in containers:
            caps = set()
            for p in c.placed:
                caps.add((p.x, p.y, p.z))
                caps.add((float(c.inner_l), p.y + p.dy, p.z))
                caps.add((float(c.inner_l), p.y, p.z + p.dz))
            caps.add((float(c.inner_l), 0.0, 0.0))
            points = sorted(caps, key=lambda pt: (-pt[0], pt[2], pt[1]))
            for (cap, y, z) in points:
                cand = _try_at_cap(cap, y, z, item, c, settings, enabled_rules)
                if cand is not None:
                    c.placed.append(cand)
                    placed = True
                    break
            if placed:
                break
        if not placed:
            unassigned.append(item)
        reporter.tick()
    return _finish_plan("extreme_point", containers, unassigned)


# ---------------------------------------------------------------------------
# Wall building: each container carries a (cap, y, z) cursor.
# ---------------------------------------------------------------------------


def wall_build(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    unassigned: list[CargoItem] = []
    cursors: dict[int, tuple] = {id(c): (float(c.inner_l), 0.0, 0.0) for c in containers}

    for item in order_items(items):
        if reporter.timed_out:
            rest = [i for i in order_items(items) if i.uid == item.uid]
            unassigned.extend(rest)
            return _finish_plan("wall_build", containers, unassigned, timed_out=True)
        placed = False
        for c in containers:
            cap, y, z = cursors[id(c)]
            cand = _try_at_cap(cap, y, z, item, c, settings, enabled_rules)
            if cand is None:
                # fall back to the deepest point of the same y/z row
                cand = _try_at_cap(float(c.inner_l), y, z, item, c, settings, enabled_rules)
            if cand is None:
                continue
            c.placed.append(cand)
            cursors[id(c)] = _advance_cursor(cand, c)
            placed = True
            break
        if not placed:
            unassigned.append(item)
        reporter.tick()
    return _finish_plan("wall_build", containers, unassigned)


# ---------------------------------------------------------------------------
# Guillotine / shelf heuristic: shelves advance door-ward along x.
# ---------------------------------------------------------------------------


def guillotine(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    unassigned: list[CargoItem] = []
    # shelves[id(c)] = list of {"cap": float, "y": float, "z": float}
    shelves: dict[int, list] = {id(c): [] for c in containers}

    for item in order_items(items):
        if reporter.timed_out:
            rest = [i for i in order_items(items) if i.uid == item.uid]
            unassigned.extend(rest)
            return _finish_plan("guillotine", containers, unassigned, timed_out=True)
        placed = False
        for c in containers:
            target = None
            for s in shelves[id(c)]:
                if s["cap"] >= max((o[0] for o in _orientations(item)), default=0.0) - 1e-9:
                    target = s
                    break
            if target is None:
                target = {"cap": float(c.inner_l), "y": 0.0, "z": 0.0}
                shelves[id(c)].append(target)
            cand = _try_at_cap(target["cap"], target["y"], target["z"], item, c, settings, enabled_rules)
            if cand is None:
                continue
            c.placed.append(cand)
            if cand.x <= 1e-9:
                target["y"] = cand.y + cand.dy
                if target["y"] + cand.dy > c.inner_w - 1e-9:
                    target["y"] = 0.0
                    target["z"] = cand.z + cand.dz
                    target["cap"] = float(c.inner_l)
                else:
                    target["cap"] = float(c.inner_l)
            else:
                target["cap"] = cand.x
            placed = True
            break
        if not placed:
            unassigned.append(item)
        reporter.tick()
    return _finish_plan("guillotine", containers, unassigned)


register("extreme_point", extreme_point)
register("wall_build", wall_build)
register("guillotine", guillotine)
