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
        self._last_report = 0.0
        self._last_done = -1

    def tick(self, n: int = 1) -> None:
        self.done = min(self.total, self.done + n)
        now = time.monotonic()
        if self.done >= self.total or self.done == 1 or now - self._last_report >= 0.2 or self.done - self._last_done >= max(1, self.total // 20):
            self._report(now)

    def _report(self, now: Optional[float] = None) -> None:
        if not self.on_progress:
            return
        now = now if now is not None else time.monotonic()
        self._last_report = now
        self._last_done = self.done
        frac = self.done / self.total
        elapsed = now - self.t0
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
        oris = [(item.l, item.w, item.h), (item.w, item.l, item.h)]
        return sorted(dict.fromkeys(oris), key=lambda d: (d[0], d[1], d[2]))
    return [(item.l, item.w, item.h)]


def _cargo_key(item: CargoItem) -> str:
    return item.cargo_type or item.packmatls or ""


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


# ---------------------------------------------------------------------------
# Shared maximal-space packing core.
#
# Candidates are free boxes (`_Space`) carved out of the container.  After each
# placement the hit space is split into the up-to-six remaining sub-boxes, so
# side/top voids are reused instead of being abandoned with the container.
# Each algorithm supplies a different `score` to order candidate spaces.
# ---------------------------------------------------------------------------


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
    out.sort(key=lambda c: (0 if c.placed else 1, c.seq_no))
    return out


def _container_waves(
    item: CargoItem,
    containers: list,
    ctx: "_Ctx",
    t_groups: dict,
    sep_sites: set,
) -> list[list]:
    """Try already-opened containers before opening an empty one."""
    eligible = _eligible_containers(item, containers, ctx, t_groups, sep_sites)
    used = [c for c in eligible if c.placed]
    empty = [c for c in eligible if not c.placed]
    waves: list[list] = []
    if used:
        waves.append(used)
    if empty:
        waves.append(empty)
    return waves


# ---------------------------------------------------------------------------
# Shared maximal-space packing core.
#
# Candidates are free boxes (`_Space`) carved out of the container.  After each
# placement the hit space is split into the up-to-six remaining sub-boxes, so
# side/top voids are reused instead of being abandoned with the container.
# Each algorithm supplies a different `score` to order candidate spaces.
# ---------------------------------------------------------------------------

_SpaceScorer = Callable[["_Space", Candidate], tuple]


def _pack_spaces(
    algorithm: str,
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
    score: _SpaceScorer,
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
        return _finish_plan(algorithm, containers, list(ordered), timed_out=True)

    for item in ordered:
        if reporter.timed_out:
            rest = [i for i in ordered if i.uid not in seen_uids]
            return _finish_plan(algorithm, containers, rest, timed_out=True)
        best: tuple[tuple, Candidate, "_Space"] | None = None
        for wave in _container_waves(item, containers, ctx, t_groups, sep_sites):
            best = None
            for c in wave:
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
                        sc = score(s, cand)
                        if best is None or sc < best[0]:
                            best = (sc, cand, s)
            if best is not None:
                break
        if best is None:
            unassigned.append(item)
        else:
            _, cand, _s = best
            spaces[id(cand.container)] = _split_spaces(spaces[id(cand.container)], cand)
            cand.container.placed.append(cand)
            seen_uids.add(item.uid)
            group = _group_of(item, t_groups)
            if group is not None and ctx.group_container.get(item.site) is None:
                ctx.group_container[item.site] = cand.container
        reporter.tick()

    return _finish_plan(algorithm, containers, unassigned)


# ---------------------------------------------------------------------------
# DBLF: deepest-bottom-left-first filling over maximal free spaces.
#
# The earlier cap-point model only tracked a handful of candidate points along
# the back wall, so leftover voids on the sides/top were never reused and each
# container was abandoned after one thin layer.  The maximal-space model splits
# the container into free boxes on every placement, so inner voids keep being
# filled and containers only open when truly full.
# ---------------------------------------------------------------------------


def dblf(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    def score(space: "_Space", cand: Candidate) -> tuple:
        return (-(cand.x + cand.dx), cand.z, cand.y)

    return _pack_spaces(
        "dblf", items, containers, settings, enabled_rules, site_groups, reporter, score
    )


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
        if cand.x > s.x + 1e-9:
            out.append(_Space(s.x, s.y, s.z, cand.x - s.x, s.dy, s.dz))
        if cand.x + cand.dx < s.x + s.dx - 1e-9:
            out.append(_Space(cand.x + cand.dx, s.y, s.z, s.x + s.dx - cand.x - cand.dx, s.dy, s.dz))
        if cand.y > s.y + 1e-9:
            out.append(_Space(s.x, s.y, s.z, s.dx, cand.y - s.y, s.dz))
        if cand.y + cand.dy < s.y + s.dy - 1e-9:
            out.append(_Space(s.x, cand.y + cand.dy, s.z, s.dx, s.y + s.dy - cand.y - cand.dy, s.dz))
        if cand.z > s.z + 1e-9:
            out.append(_Space(s.x, s.y, s.z, s.dx, s.dy, cand.z - s.z))
        if cand.z + cand.dz < s.z + s.dz - 1e-9:
            out.append(_Space(s.x, s.y, cand.z + cand.dz, s.dx, s.dy, s.z + s.dz - cand.z - cand.dz))
    return _prune_spaces(out)


def _prune_spaces(spaces: list[_Space]) -> list[_Space]:
    valid = [s for s in spaces if s.dx > 1.0 and s.dy > 1.0 and s.dz > 1.0]
    kept: list[_Space] = []
    for i, s in enumerate(valid):
        contained = False
        for j, t in enumerate(valid):
            if i == j:
                continue
            if (
                t.x <= s.x + 1e-6
                and t.y <= s.y + 1e-6
                and t.z <= s.z + 1e-6
                and t.x + t.dx >= s.x + s.dx - 1e-6
                and t.y + t.dy >= s.y + s.dy - 1e-6
                and t.z + t.dz >= s.z + s.dz - 1e-6
            ):
                same = (
                    abs(t.x - s.x) <= 1e-6
                    and abs(t.y - s.y) <= 1e-6
                    and abs(t.z - s.z) <= 1e-6
                    and abs(t.dx - s.dx) <= 1e-6
                    and abs(t.dy - s.dy) <= 1e-6
                    and abs(t.dz - s.dz) <= 1e-6
                )
                if same and j > i:
                    continue
                contained = True
                break
        if not contained:
            kept.append(s)
    return kept


def maximal_space(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    def score(space: "_Space", cand: Candidate) -> tuple:
        # deepest-first, then lowest z, then leftmost y, then tightest space
        return (-(cand.x + cand.dx), cand.z, cand.y, space.volume())

    return _pack_spaces(
        "maxspace", items, containers, settings, enabled_rules, site_groups, reporter, score
    )


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
        by_type.setdefault(_cargo_key(it), []).append(it)
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
            for wave in _container_waves(item, containers, ctx, t_groups, sep_sites):
                best = None
                for c in wave:
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
                            score = (-x0, s.z, s.y, s.volume() / max(dx * dy * dz, 1e-9))
                            if best is None or score < best[0]:
                                best = (score, cand, s)
                if best is not None:
                    break
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
