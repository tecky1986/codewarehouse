"""Placement strategies. All strategies share the same rule-checker chain.

Coordinate convention:
  - x axis: 0 at the door, increasing toward the inner end wall (x = inner_l).
  - "cap" candidate model: a candidate is (cap, y, z).  cap is the farthest
    back-face bound for the new item: the item is placed flush with its back
    face at cap, i.e. item.x = cap - dx (deepest possible inside [0, cap]).
  - Initial candidate for a container: (inner_l, 0, 0) -> fill from the
    inner end toward the door (inside-out, R17).
  - After placing an item at [x, x+dx] with (y, z, dx, dy, dz):
      * front face  -> new cap = x (items in front of it, door-ward)
      * side        -> same cap, y + dy
      * top         -> same cap, z + dz
  - Candidate sort key: (-cap, z, y): fill the innermost wall first,
    then from the floor up, then along the width.
  - load_seq is rewritten after packing: innermost, then bottom-up, then y.
"""

import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from packing_engine.groups import (
    group_total,
    order_items,
    site_separate_sites,
    site_together_groups,
)
from packing_engine.model import Candidate, CargoItem, ContainerInstance, Plan
from packing_engine.rules import CheckContext, run_checkers


class ProgressReporter:
    def __init__(self, total: int, deadline_s: float, on_progress: Optional[Callable[[float, float], None]] = None):
        self.total = max(total, 1)
        self.done = 0
        self.t0 = time.monotonic()
        self._immediate_timeout = deadline_s <= 0.0
        self.deadline = self.t0 + max(deadline_s, 0.0)
        self.on_progress = on_progress

    def tick(self, n: int = 1) -> None:
        self.done = min(self.total, self.done + n)
        self._report()

    def _report(self) -> None:
        if not self.on_progress:
            return
        frac = self.done / self.total
        elapsed = time.monotonic() - self.t0
        eta = (elapsed / self.done * (self.total - self.done)) if 0 < self.done < self.total else 0.0
        self.on_progress(frac, eta)

    @property
    def timed_out(self) -> bool:
        if self._immediate_timeout:
            return True
        return time.monotonic() > self.deadline

    def remaining(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


# --------------------------------------------------------------------------


@dataclass
class _Ctx:
    containers: list
    items: list
    settings: dict
    enabled_rules: list
    site_groups: list
    reporter: ProgressReporter
    group_container: dict = field(default_factory=dict)


def _orientations(item: CargoItem) -> list[tuple]:
    if item.rotatable:
        return [(item.l, item.w, item.h), (item.w, item.l, item.h)]
    return [(item.l, item.w, item.h)]


def _is_separate_site_conflict(item: CargoItem, container: ContainerInstance, sep_sites: set) -> bool:
    if item.site not in sep_sites:
        return False
    return any(p.item.site == item.site for p in container.placed)


def _group_of(item: CargoItem, t_groups: dict) -> list[CargoItem] | None:
    if not item.site:
        return None
    return t_groups.get(item.site)


def _group_fits(group: list[CargoItem], c: ContainerInstance) -> bool:
    vol, gross = group_total(group)
    return c.remaining_volume + 1e-6 >= vol and c.remaining_payload + 1e-6 >= gross


def _first_violation(cand: Candidate, ctx: _Ctx) -> tuple[str, str] | None:
    check_ctx = CheckContext(settings=ctx.settings, placed=cand.container.placed)
    violations = run_checkers(cand, check_ctx, ctx.enabled_rules)
    if not violations:
        return None
    hard = {"bounds": 0, "collision": 1, "payload": 2}
    violations.sort(key=lambda v: hard.get(v[0], 100))
    return violations[0]


def _try_place_at_cap(
    cap: float,
    y: float,
    z: float,
    item: CargoItem,
    container: ContainerInstance,
    ctx: _Ctx,
) -> Candidate | None:
    """Place item flush at back face `cap` (x = cap - dx); return cand or None."""
    load_seq = len(container.placed) + 1
    z_max = container.max_z
    for (dx, dy, dz) in _orientations(item):
        x = cap - dx
        if x < -1e-9 or dy > container.inner_w - y + 1e-9 or dz > z_max - z + 1e-9:
            continue
        cand = Candidate(
            item=item,
            container=container,
            x=max(0.0, x),
            y=y,
            z=z,
            dx=dx,
            dy=dy,
            dz=dz,
            load_seq=load_seq,
        )
        if _first_violation(cand, ctx) is None:
            return cand
    return None


def _expand_candidates(candidates: list, cand: Candidate, prev_cap: float) -> None:
    z_max = cand.container.max_z
    for p in (
        (prev_cap, cand.y + cand.dy, cand.z),
        (prev_cap, cand.y, cand.z + cand.dz) if cand.z + cand.dz <= z_max + 1e-9 else None,
        (cand.x, cand.y, cand.z),
    ):
        if p is not None and p not in candidates:
            candidates.append(p)
    candidates.sort(key=lambda p: (-p[0], p[2], p[1]))


def _eligible_containers(
    item: CargoItem,
    containers: list,
    ctx: _Ctx,
    t_groups: dict,
    sep_sites: set,
) -> list:
    out = []
    for c in containers:
        if _is_separate_site_conflict(item, c, sep_sites):
            continue
        group = _group_of(item, t_groups)
        if group is not None:
            if ctx.group_container.get(item.site) is None:
                if not _group_fits(group, c):
                    continue
            elif ctx.group_container[item.site] is not c:
                continue
        out.append(c)
    return out


def _unassign_reason(item: CargoItem, containers: list, ctx: _Ctx) -> str:
    seen = set()
    for c in containers:
        check = CheckContext(settings=ctx.settings, placed=c.placed)
        for (dx, dy, dz) in _orientations(item):
            cand = Candidate(
                item=item,
                container=c,
                x=0.0,
                y=0.0,
                z=0.0,
                dx=dx,
                dy=dy,
                dz=dz,
                load_seq=len(c.placed) + 1,
            )
            for name, msg in run_checkers(cand, check, ctx.enabled_rules):
                if name not in ("bounds", "collision"):
                    seen.add(msg)
    return next(iter(seen)) if seen else "无可用箱位"


# ---------------------------------------------------------------------------
# DBLF: deepest-first filling with cap candidate points.
# ---------------------------------------------------------------------------


def dblf(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    ctx = _Ctx(
        containers=containers,
        items=items,
        settings=settings,
        enabled_rules=enabled_rules,
        site_groups=site_groups,
        reporter=reporter,
    )
    t_groups = site_together_groups(items, site_groups)
    sep_sites = site_separate_sites(items, site_groups)
    cands: dict[int, list] = {id(c): [(float(c.inner_l), 0.0, 0.0)] for c in containers}
    unassigned: list[CargoItem] = []
    ordered = order_items(items)
    seen_uids: set = set()

    if reporter.timed_out:
        return _finish_plan("dblf", containers, list(ordered), timed_out=True)

    for item in ordered:
        if reporter.timed_out:
            rest = [i for i in ordered if i.uid not in seen_uids]
            return _finish_plan("dblf", containers, rest, timed_out=True)
        chosen_cand = None
        for c in _eligible_containers(item, containers, ctx, t_groups, sep_sites):
            for (cap, y, z) in list(cands[id(c)]):
                cand = _try_place_at_cap(cap, y, z, item, c, ctx)
                if cand is not None:
                    c.placed.append(cand)
                    _expand_candidates(cands[id(c)], cand, cap)
                    chosen_cand = cand
                    break
            if chosen_cand is not None:
                break
        if chosen_cand is not None:
            seen_uids.add(item.uid)
            group = _group_of(item, t_groups)
            if group is not None and ctx.group_container.get(item.site) is None:
                ctx.group_container[item.site] = chosen_cand.container
        else:
            reason = _unassign_reason(item, containers, ctx)
            unassigned.append(item)
        reporter.tick()

    return _finish_plan("dblf", containers, unassigned)


# ---------------------------------------------------------------------------
# Maximal Space: keep a list of empty boxes; split on placement.
# ---------------------------------------------------------------------------


class _Space:
    __slots__ = ("x", "y", "z", "dx", "dy", "dz")

    def __init__(self, x, y, z, dx, dy, dz):
        self.x, self.y, self.z = x, y, z
        self.dx, self.dy, self.dz = dx, dy, dz

    def volume(self) -> float:
        return self.dx * self.dy * self.dz


def _split_spaces(spaces: list[_Space], cand: Candidate) -> list[_Space]:
    out = []
    for s in spaces:
        overlaps = (
            cand.x < s.x + s.dx - 1e-9
            and s.x < cand.x + cand.dx - 1e-9
            and cand.y < s.y + s.dy - 1e-9
            and s.y < cand.y + cand.dy - 1e-9
            and cand.z < s.z + s.dz - 1e-9
            and s.z < cand.z + cand.dz - 1e-9
        )
        if not overlaps:
            out.append(s)
            continue
        if cand.x > s.x:
            out.append(_Space(s.x, s.y, s.z, cand.x - s.x, s.dy, s.dz))
        if cand.x + cand.dx < s.x + s.dx:
            out.append(_Space(cand.x + cand.dx, s.y, s.z, s.x + s.dx - cand.x - cand.dx, s.dy, s.dz))
        if cand.y > s.y:
            out.append(_Space(cand.x, s.y, s.z, cand.dx, cand.y - s.y, s.dz))
        if cand.y + cand.dy < s.y + s.dy:
            out.append(_Space(cand.x, cand.y + cand.dy, s.z, cand.dx, s.y + s.dy - cand.y - cand.dy, s.dz))
        if cand.z > s.z:
            out.append(_Space(cand.x, cand.y, s.z, cand.dx, cand.dy, cand.z - s.z))
        if cand.z + cand.dz < s.z + s.dz:
            out.append(_Space(cand.x, cand.y, cand.z + cand.dz, cand.dx, cand.dy, s.z + s.dz - cand.z - cand.dz))
    return out


def maximal_space(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    ctx = _Ctx(
        containers=containers,
        items=items,
        settings=settings,
        enabled_rules=enabled_rules,
        site_groups=site_groups,
        reporter=reporter,
    )
    t_groups = site_together_groups(items, site_groups)
    sep_sites = site_separate_sites(items, site_groups)
    spaces: dict[int, list[_Space]] = {
        id(c): [_Space(0.0, 0.0, 0.0, float(c.inner_l), float(c.inner_w), c.max_z)]
        for c in containers
    }
    unassigned: list[CargoItem] = []
    ordered = order_items(items)
    seen_uids: set = set()

    if reporter.timed_out:
        return _finish_plan("maxspace", containers, list(ordered), timed_out=True)

    for item in ordered:
        if reporter.timed_out:
            rest = [i for i in ordered if i.uid not in seen_uids]
            return _finish_plan("maxspace", containers, rest, timed_out=True)
        best: tuple[float, Candidate, _Space] | None = None
        for c in _eligible_containers(item, containers, ctx, t_groups, sep_sites):
            check_ctx = CheckContext(settings=settings, placed=c.placed)
            for s in list(spaces[id(c)]):
                for (dx, dy, dz) in _orientations(item):
                    if dx > s.dx + 1e-9 or dy > s.dy + 1e-9 or dz > s.dz + 1e-9:
                        continue
                    x0 = s.x + max(0.0, s.dx - dx)
                    score = (-x0, s.z, s.y, s.volume() / max(dx * dy * dz, 1e-9))
                    cand = Candidate(
                        item=item,
                        container=c,
                        x=x0,
                        y=s.y,
                        z=s.z,
                        dx=dx,
                        dy=dy,
                        dz=dz,
                        load_seq=len(c.placed) + 1,
                    )
                    if _first_violation(cand, ctx):
                        continue
                    if best is None or score < best[0]:
                        best = (score, cand, s)
        if best is None:
            unassigned.append(item)
        else:
            _, cand, s = best
            spaces[id(cand.container)] = _split_spaces(spaces[id(cand.container)], cand)
            cand.container.placed.append(cand)
            seen_uids.add(item.uid)
            group = _group_of(item, t_groups)
            if group is not None and ctx.group_container.get(item.site) is None:
                ctx.group_container[item.site] = cand.container
        reporter.tick()

    return _finish_plan("maxspace", containers, unassigned)


# ---------------------------------------------------------------------------
# Wall Fill: dense per-cargo_type layers.  Items are grouped by cargo_type,
# largest single-item volume first so big box types claim whole floor
# layers; small box types (threshold _MEDIUM_VOL) fill the gaps left over,
# smallest first, so nothing large is ever blocked by smalls.
# ---------------------------------------------------------------------------

_MEDIUM_VOL = 1.0  # m3; a cargo_type is "small" when its smallest item is below this.


def _wall_fill_order(items: list[CargoItem]) -> list[tuple[str, list[CargoItem]]]:
    """(cargo_type, [items by single-item volume desc]) groups, ordered by
    max single-item volume desc.

    Largest individual box types (IB-1, GB-3, FD-1 …) go first so they can
    claim whole floor layers; smaller types (VEN, OUTCASE …) fill the gaps
    left behind.  Within each group, heaviest-first is the secondary key.
    """
    by_type: dict[str, list[CargoItem]] = {}
    for it in items:
        by_type.setdefault(it.cargo_type or "", []).append(it)
    groups: list[tuple[str, list[CargoItem]]] = []
    for cto, group in by_type.items():
        ordered = sorted(group, key=lambda i: (-i.volume_m3(), -i.gross, i.uid))
        groups.append((cto, ordered))
    groups.sort(key=lambda kv: -max(i.volume_m3() for i in kv[1]))
    return groups


def wall_fill(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    ctx = _Ctx(
        containers=containers,
        items=items,
        settings=settings,
        enabled_rules=enabled_rules,
        site_groups=site_groups,
        reporter=reporter,
    )
    t_groups = site_together_groups(items, site_groups)
    sep_sites = site_separate_sites(items, site_groups)
    spaces: dict[int, list[_Space]] = {
        id(c): [_Space(0.0, 0.0, 0.0, float(c.inner_l), float(c.inner_w), c.max_z)]
        for c in containers
    }
    unassigned: list[CargoItem] = []
    groups = _wall_fill_order(items)
    seen_uids: set = set()

    if reporter.timed_out:
        return _finish_plan("wall_fill", containers, [i for _, g in groups for i in g], timed_out=True)

    # Phase 1: wall groups — largest box types claim floor layers.
    # Phase 2: small box types fill the gaps, ascending height so short
    # boxes lay the low floors and taller boxes stack on top.
    small_types = {cto for cto, g in groups if g and min(i.volume_m3() for i in g) < _MEDIUM_VOL}
    wall_groups = [gv for cto, gv in groups if cto not in small_types]
    fill_groups = [gv for cto, gv in groups if cto in small_types]
    fill_groups.sort(key=lambda gv: min(min(i.l, i.w, i.h) for i in gv))

    def _try_place_all(group: list[CargoItem]) -> None:
        for item in group:
            if item.uid in seen_uids or reporter.timed_out:
                continue
            best: tuple[tuple, Candidate, _Space] | None = None
            for c in _eligible_containers(item, containers, ctx, t_groups, sep_sites):
                check_ctx = CheckContext(settings=settings, placed=c.placed)
                for s in list(spaces[id(c)]):
                    for (dx, dy, dz) in _orientations(item):
                        if dx > s.dx + 1e-9 or dy > s.dy + 1e-9 or dz > s.dz + 1e-9:
                            continue
                        x0 = s.x + max(0.0, s.dx - dx)
                        cand = Candidate(
                            item=item,
                            container=c,
                            x=x0,
                            y=s.y,
                            z=s.z,
                            dx=dx,
                            dy=dy,
                            dz=dz,
                            load_seq=len(c.placed) + 1,
                        )
                        if _first_violation(cand, ctx):
                            continue
                        # Wall groups: low-level-first toward the door so
                        # boxes form continuous layers (z, y, tightness).
                        # Fill groups: smallest-first (height ascending) and
                        # tightest-gap-first so a floor layer is completed
                        # before moving to the next (z, height, tightness, y).
                        if item.volume_m3() < _MEDIUM_VOL:
                            score = (s.z, dz, s.volume() / max(dx * dy * dz, 1e-9), s.y)
                        else:
                            score = (s.z, s.y, s.volume() / max(dx * dy * dz, 1e-9))
                        if best is None or score < best[0]:
                            best = (score, cand, s)
            if best is None:
                unassigned.append(item)
                continue
            _, cand, _s = best
            spaces[id(cand.container)] = _split_spaces(spaces[id(cand.container)], cand)
            cand.container.placed.append(cand)
            seen_uids.add(item.uid)
            grp = _group_of(item, t_groups)
            if grp is not None and ctx.group_container.get(item.site) is None:
                ctx.group_container[item.site] = cand.container
            reporter.tick()

    for group in wall_groups:
        if reporter.timed_out:
            break
        _try_place_all(group)
    for group in fill_groups:
        if reporter.timed_out:
            break
        _try_place_all(group)

    return _finish_plan("wall_fill", containers, unassigned)


def assign_load_seq(containers: list) -> None:
    """Rewrite load_seq: lower z-levels first, then deepest back face,
    then along width, then uid for determinism.

    Sorting by (z, -(x+dx), y, uid) ensures:
    - Lower z-levels are loaded first (supports before things on top).
    - Within the same z-level, deeper items (larger back face x+dx)
      are loaded before shallower ones, so the forklift can reach each
      item without crossing already-placed boxes.
    - uid breaks ties for stable ordering.
    """
    for c in containers:
        ordered = sorted(c.placed, key=lambda p: (p.z, -(p.x + p.dx), p.y, p.item.uid))
        for i, p in enumerate(ordered, start=1):
            p.load_seq = i
        c.placed[:] = ordered


def _finish_plan(algorithm: str, containers: list, unassigned: list, timed_out: bool = False) -> Plan:
    assign_load_seq(containers)
    return Plan(algorithm=algorithm, containers=containers, unassigned=unassigned, timed_out=timed_out)


def assign_load_seq_public(containers: list) -> None:
    """Public alias so other modules/tests can rewrite load_seq after packing."""
    assign_load_seq(containers)


ALGORITHMS = {
    "dblf": dblf,
    "maxspace": maximal_space,
    "wall_fill": wall_fill,
}


def register(name, fn) -> None:
    ALGORITHMS[name] = fn
