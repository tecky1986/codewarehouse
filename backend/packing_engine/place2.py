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
        oris = [(item.l, item.w, item.h), (item.w, item.l, item.h)]
        return sorted(dict.fromkeys(oris), key=lambda d: (d[0], d[1], d[2]))
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
    z_max = c.max_z
    check_ctx = CheckContext(settings=settings, placed=c.placed)
    for (dx, dy, dz) in _orientations(item):
        x0 = cap - dx
        if x0 < -1e-9:
            continue
        if dy > c.inner_w - y + 1e-9 or dz > z_max - z + 1e-9:
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


def _advance_cursor(
    cand: Candidate,
    c: ContainerInstance,
    cap: float,
    row_max_dx: float,
    row_max_dz: float,
    layer_max_dx: float,
) -> tuple[float, float, float, float, float, float]:
    """Advance the wall cursor after placing cand.

    Returns (cap, y, z, row_max_dx, row_max_dz, layer_max_dx).

    Within a row (y direction) the cap stays fixed.  When the row is full
    (y overflows inner_w) the cursor moves to the next z-row, keeping the
    cap unchanged.  When z overflows max_z (inner_h or door_h) the cap is
    pushed door-ward by the layer's deepest item and z resets to 0.
    """
    z_max = c.max_z
    new_y = cand.y + cand.dy
    new_row_max_dx = max(row_max_dx, cand.dx)
    new_row_max_dz = max(row_max_dz, cand.dz)
    new_layer_max_dx = max(layer_max_dx, cand.dx)

    if new_y < c.inner_w - 1e-9:
        # same row: advance along y, cap unchanged
        return (cap, new_y, cand.z, new_row_max_dx, new_row_max_dz, new_layer_max_dx)

    # row full: move to next z-row, cap unchanged
    new_z = cand.z + new_row_max_dz
    if new_z >= z_max - 1e-9:
        # z-layer full: push cap door-ward, reset z and y
        new_cap = cap - new_layer_max_dx
        if new_cap <= 1e-9:
            return (float(c.inner_l), 0.0, 0.0, 0.0, 0.0, 0.0)
        return (new_cap, 0.0, 0.0, 0.0, 0.0, 0.0)
    return (cap, 0.0, new_z, 0.0, 0.0, new_layer_max_dx)


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
    ordered = order_items(items)
    seen_uids: set = set()

    if reporter.timed_out:
        return _finish_plan("extreme_point", containers, list(ordered), timed_out=True)

    for item in ordered:
        if reporter.timed_out:
            rest = [i for i in ordered if i.uid not in seen_uids]
            unassigned.extend(rest)
            return _finish_plan("extreme_point", containers, unassigned, timed_out=True)
        seen_uids.add(item.uid)
        placed = False
        used = [c for c in containers if c.placed]
        empty = [c for c in containers if not c.placed]
        for wave in (used, empty):
            best = None
            best_score = None
            for c in wave:
                caps = set()
                for p in c.placed:
                    back = p.x + p.dx
                    caps.add((p.x, p.y, p.z))
                    caps.add((back, p.y + p.dy, p.z))
                    caps.add((back, p.y, p.z + p.dz))
                    caps.add((float(c.inner_l), p.y + p.dy, p.z))
                    caps.add((float(c.inner_l), p.y, p.z + p.dz))
                    caps.add((p.x, p.y + p.dy, p.z))
                    caps.add((p.x, p.y, p.z + p.dz))
                caps.add((float(c.inner_l), 0.0, 0.0))
                for (cap, y, z) in caps:
                    cand = _try_at_cap(cap, y, z, item, c, settings, enabled_rules)
                    if cand is None:
                        continue
                    score = (-(cand.x + cand.dx), cand.z, cand.y, cand.dx, cand.x)
                    if best is None or score < best_score:
                        best = cand
                        best_score = score
            if best is not None:
                best.container.placed.append(best)
                placed = True
                break
        if not placed:
            unassigned.append(item)
        reporter.tick()
    return _finish_plan("extreme_point", containers, unassigned)


# ---------------------------------------------------------------------------
# Wall build and guillotine strategies were retired; the active core set now
# uses layer-based packing, maximal spaces, extreme points, bottom-left-back
# candidate ordering, and LNS local improvement.
# ---------------------------------------------------------------------------


from packing_engine.lns import lns as _lns_fn

register("extreme_point", extreme_point)
register("lns", _lns_fn)

