"""Plan verification by forward loading replay and reverse unloading replay.

The verifier replays the per-container load sequence step by step on the
empty container, then replays the unloading sequence in reverse.  Every
step is checked against the physical forklift loading model:

- The forklift works from the door (x = 0) toward the inner end wall
  (x = inner_l).  At each placement step the forks carry the new box along
  the x axis at working height z = p.z .. p.z + p.dz.
- A box q already in the container blocks the forks when it stands above
  the forks' working height (q.z + q.dz > p.z), its y band overlaps the
  target's, and the forks must cross q's x span to reach the target.
- Forks can slide under q when q's top face is at or below the forks'
  bottom; they cannot pass horizontally past q's sides.

Error codes
-----------
E101  外侧货物阻挡内侧货物 (an outer box shields the path to an inner box)
E102  当前排尚未完成 (a new row is opened before the current row is full)
E103  上层货物缺少支撑 (elevated box has no support under its footprint)
E104  叉车进入路径被阻挡 (fork entry path blocked by a placed box)
E105  货物放置路径发生碰撞 (placement path collides with a placed box)
E106  货叉无法退出 (forks cannot be withdrawn during unloading)
E107  叉车无法倒退出柜 (forklift cannot reverse out of the container)
E108  门架举升高度不足 (box top exceeds the door frame / mast height)
E109  货物无法通过柜门 (box footprint does not fit through the door)
E110  货物超过下层承重 (load on a supporting box exceeds its max_load)
E111  装载顺序存在循环依赖 (circular stacking dependency in the order)
E112  未预留叉车作业空间 (no forklift working space was reserved)

The replay model supports 逐步动画回放 (animation frames are the per-step
state snapshots in ContainerReport.frames) and 反向模拟卸货 (reverse
unloading simulation, see ContainerReport.unload_frames).
"""

from dataclasses import dataclass, field
from typing import Optional

from packing_engine.geometry import EPS
from packing_engine.model import Candidate, ContainerInstance, Plan


# --------------------------------------------------------------------------
# Result model
# --------------------------------------------------------------------------


@dataclass
class StepResult:
    seq: int
    uid: str
    ok: bool = True
    errors: list[tuple[str, str]] = field(default_factory=list)

    def add(self, code: str, msg: str) -> None:
        self.ok = False
        self.errors.append((code, msg))


@dataclass
class ContainerReport:
    label: str
    steps: list[StepResult] = field(default_factory=list)
    frames: list[list[str]] = field(default_factory=list)
    unload_ok: bool = True
    unload_errors: list[tuple[str, str]] = field(default_factory=list)
    unload_steps: list[StepResult] = field(default_factory=list)
    unload_frames: list[list[str]] = field(default_factory=list)

    @property
    def errors(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for s in self.steps:
            out.extend(s.errors)
        out.extend(self.unload_errors)
        for s in self.unload_steps:
            out.extend(s.errors)
        return out

    @property
    def error_codes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for code, _ in self.errors:
            counts[code] = counts.get(code, 0) + 1
        return counts

    @property
    def ok(self) -> bool:
        return not self.errors


@dataclass
class PlanReport:
    algorithm: str
    containers: list[ContainerReport] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.containers)

    @property
    def error_codes(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.containers:
            for code, n in c.error_codes.items():
                counts[code] = counts.get(code, 0) + n
        return counts

    def summary(self) -> dict:
        return {
            "algorithm": self.algorithm,
            "ok": self.ok,
            "error_codes": self.error_codes,
            "containers": [
                {
                    "label": c.label,
                    "ok": c.ok,
                    "steps": len(c.steps),
                    "unload_ok": c.unload_ok,
                    "errors": c.error_codes,
                }
                for c in self.containers
            ],
        }

    def dump_json(self) -> dict:
        out = self.summary()
        out["containers"] = []
        for c in self.containers:
            out["containers"].append({
                "label": c.label,
                "ok": c.ok,
                "unload_ok": c.unload_ok,
                "errors": c.error_codes,
                "steps": [
                    {"seq": s.seq, "uid": s.uid, "ok": s.ok,
                     "errors": list(s.errors)}
                    for s in c.steps
                ],
                "frames": c.frames,
                "unload_steps": [
                    {"seq": s.seq, "uid": s.uid, "ok": s.ok,
                     "errors": list(s.errors)}
                    for s in c.unload_steps
                ],
                "unload_frames": c.unload_frames,
            })
        return out


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _y_overlap(a_y: float, a_dy: float, b_y: float, b_dy: float) -> bool:
    return a_y < b_y + b_dy - EPS and b_y < a_y + a_dy - EPS


def _x_overlap(a_x: float, a_dx: float, b_x: float, b_dx: float) -> bool:
    return a_x < b_x + b_dx - EPS and b_x < a_x + a_dx - EPS


def _box_below(top: Candidate, placed: list[Candidate]) -> list[Candidate]:
    """Placed boxes whose top face is flush with top's bottom face."""
    return [
        p
        for p in placed
        if abs(p.z + p.dz - top.z) < EPS
        and _x_overlap(p.x, p.dx, top.x, top.dx)
        and _y_overlap(p.y, p.dy, top.y, top.dy)
    ]


def _box_above(bottom: Candidate, placed: list[Candidate]) -> list[Candidate]:
    """Placed boxes resting on bottom's top face."""
    return [
        p
        for p in placed
        if abs(p.z - bottom.z - bottom.dz) < EPS
        and _x_overlap(p.x, p.dx, bottom.x, bottom.dx)
        and _y_overlap(p.y, p.dy, bottom.y, bottom.dy)
    ]


def _z_level(p: Candidate) -> float:
    """Quantised z-level (layer) of a box."""
    return round(p.z / 100.0)


def _fork_blocker(p: Candidate, placed: list[Candidate]) -> Optional[Candidate]:
    """Box blocking the forks as they advance from the door to p.

    The forks carry p along x at height p.z .. p.z + p.dz.  A placed box q
    blocks the travel when the forks must cross q's volume: q's y band
    overlaps p's, q rises above the forks' bottom (q.z + q.dz > p.z), and
    q intrudes into the corridor the forks sweep (their x intervals
    overlap).  Forks can slide under q when q's top is at or below p.z.
    """
    for q in placed:
        if q is p:
            continue
        if not _x_overlap(q.x, q.dx, p.x, p.dx):
            continue
        if not _y_overlap(q.y, q.dy, p.y, p.dy):
            continue
        if q.z + q.dz > p.z + EPS:
            return q
    return None


def _row_front_face(placed: list[Candidate], z_level: float, y: float, dy: float) -> float:
    """Deepest front face (min x) of any box in the same y-band at z_level.

    A row is "complete" when its front face has reached the door (x = 0).
    Returns min x over boxes in the band, or 0.0 when the band is empty
    (an empty band is trivially complete).
    """
    xs = [
        p.x
        for p in placed
        if _z_level(p) == z_level
        and _y_overlap(p.y, p.dy, y, dy)
    ]
    return min(xs) if xs else 0.0


# --------------------------------------------------------------------------
# forward replay
# --------------------------------------------------------------------------


def _verify_container_forward(c: ContainerInstance) -> ContainerReport:
    rep = ContainerReport(label=c.label)
    by_seq = {p.load_seq: p for p in c.placed}
    ordered = [by_seq[s] for s in sorted(by_seq)]
    placed: list[Candidate] = []
    placed_ids: list[str] = []

    # open rows: z_level -> list of y-bands opened so far
    open_rows: dict[float, list[tuple[float, float]]] = {}

    for p in ordered:
        step = StepResult(seq=p.load_seq, uid=p.item.uid)
        zl = _z_level(p)

        # --- E102: row discipline ----------------------------------------
        # A row is (z-level, y-band).  Within one z-level, y-bands must be
        # opened in increasing y order, and each band must be filled to the
        # door (front face x = 0) before the next band opens.  Moving to a
        # higher z-level (stacking) does not count as opening a new row.
        bands = open_rows.get(zl, [])
        new_band = not any(
            _y_overlap(by, bdy, p.y, p.dy) for by, bdy in bands
        )
        if new_band:
            for by, bdy in bands:
                front = _row_front_face(placed, zl, by, bdy)
                if front > EPS:
                    step.add("E102", f"当前排（z={zl*100}, y={by:.0f}）尚未完成")
                    break
            bands.append((p.y, p.dy))
            open_rows[zl] = bands

        # --- E103 / E110: supports and load capacity -------------------
        if p.z > EPS:
            under = _box_below(p, placed)
            if not under:
                step.add("E103", "缺少支撑")
            else:
                for b in under:
                    cap = b.item.max_load
                    if cap is None:
                        continue
                    load = sum(q.item.gross for q in _box_above(b, placed)) + p.item.gross
                    if load > cap + EPS:
                        step.add("E110", f"超过下层承重 {cap:.0f} kg")
                        break

        # --- E101 / E104: fork entry path --------------------------------
        blocker = _fork_blocker(p, placed)
        if blocker is not None:
            step.add("E104", f"货叉进入路径被 {blocker.item.uid} 阻挡")
            if p.x + p.dx > blocker.x + blocker.dx + EPS:
                step.add("E101", f"外侧货物 {blocker.item.uid} 阻挡内侧货物 {p.item.uid}")

        # --- E105: placement path collision -----------------------------
        for q in placed:
            if q is p:
                continue
            if (
                _x_overlap(q.x, q.dx, p.x, p.dx)
                and _y_overlap(q.y, q.dy, p.y, p.dy)
                and q.z + q.dz > p.z + EPS
                and p.z + p.dz > q.z + EPS
                and not abs(q.z + q.dz - p.z) < EPS
                and not abs(q.z - (p.z + p.dz)) < EPS
            ):
                step.add("E105", f"放置路径与 {q.item.uid} 碰撞")
                break

        # --- E108: mast lift height --------------------------------------
        door_h = getattr(c, "door_h", None) or c.inner_h
        if p.z + p.dz > door_h + EPS:
            step.add("E108", "门架举升高度不足")

        # --- E109: door passage -------------------------------------------
        door_w = getattr(c, "door_w", None)
        if door_w is not None and p.dy > door_w + EPS:
            step.add("E109", f"货物宽度 {p.dy:.0f} mm 超过柜门 {door_w} mm")

        # --- E112: forklift working space ---------------------------------
        # After placing p the forks must be able to withdraw through the
        # corridor in front of p (x < p.x).  If p fills the whole width
        # and another box already occupies the same y-band closer to the
        # door at a higher level, the forklift has no working space.
        full_width = p.dy >= c.inner_w - 1e-9
        front_occupied = any(
            _y_overlap(q.y, q.dy, p.y, p.dy)
            and q.x + q.dx <= p.x + EPS
            and q.z + q.dz > p.z + EPS
            for q in placed
        )
        if full_width and front_occupied:
            step.add("E112", "未预留叉车作业空间")

        rep.steps.append(step)
        placed.append(p)
        placed_ids.append(p.item.uid)
        rep.frames.append(list(placed_ids))

    return rep


# --------------------------------------------------------------------------
# reverse unloading replay
# --------------------------------------------------------------------------


def _verify_container_unload(c: ContainerInstance) -> ContainerReport:
    rep = ContainerReport(label=c.label)
    all_placed = sorted(c.placed, key=lambda p: p.load_seq)
    remaining: list[Candidate] = list(all_placed)
    remaining_ids: list[str] = [p.item.uid for p in all_placed]

    seq = len(all_placed)
    for p in reversed(all_placed):
        rest = [q for q in remaining if q is not p]
        step = StepResult(seq=seq, uid=p.item.uid)

        # a box may be removed only when nothing sits on top of it
        above = _box_above(p, rest)
        if above:
            step.add("E103", f"顶部仍有 {len(above)} 件货物，无法取出")

        # the forks must be able to withdraw: nothing in front of p in the
        # same y-band rising above the forks' working height
        blocker = _fork_blocker(p, rest)
        if blocker is not None:
            step.add("E106", f"货叉无法退出，被 {blocker.item.uid} 阻挡")

        if step.errors:
            rep.unload_ok = False
            rep.unload_errors.extend(step.errors)
            seq -= 1
            rep.unload_steps.append(step)
            rep.unload_frames.append(list(remaining_ids))
            continue

        remaining.remove(p)
        remaining_ids.remove(p.item.uid)
        seq -= 1
        rep.unload_steps.append(step)
        rep.unload_frames.append(list(remaining_ids))

    # E107 -- after all boxes are out the forklift reverses out of the
    # door.  Leftover boxes (that could not be unloaded) block the lane.
    if remaining:
        rep.unload_ok = False
        rep.unload_errors.append(
            ("E107", f"无法倒退出柜，残留 {len(remaining)} 件货物")
        )
    return rep


# --------------------------------------------------------------------------
# circular dependency detection (E111)
# --------------------------------------------------------------------------


def _check_cycle(c: ContainerInstance) -> list[tuple[str, str, str]]:
    """Detect load-order cycles in the 'rests on' relation.

    A box sitting on another must be loaded later than its supports.
    Returns (code, message, uid) triples so the error attaches to the
    offending placement.
    """
    errors: list[tuple[str, str, str]] = []
    graph: dict[str, set[str]] = {}
    for p in c.placed:
        under = _box_below(p, c.placed)
        if not under:
            continue
        graph.setdefault(p.item.uid, set())
        for b in under:
            graph[p.item.uid].add(b.item.uid)
            if b.load_seq > p.load_seq:
                errors.append(
                    ("E111", f"{p.item.uid} 压在 {b.item.uid} 上却更早装入", p.item.uid)
                )

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {p.item.uid: WHITE for p in c.placed}

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in graph.get(u, ()):
            if color.get(v, WHITE) == GRAY:
                return True
            if color.get(v, WHITE) == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    for p in c.placed:
        uid = p.item.uid
        if color[uid] == WHITE and dfs(uid):
            errors.append(("E111", "装载顺序存在循环依赖", uid))
            break
    return errors


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------


def verify_plan(plan: Plan) -> PlanReport:
    report = PlanReport(algorithm=plan.algorithm)
    for c in plan.containers:
        fwd = _verify_container_forward(c)
        unload = _verify_container_unload(c)
        fwd.unload_ok = unload.unload_ok
        fwd.unload_errors = unload.unload_errors
        fwd.unload_steps = unload.unload_steps
        fwd.unload_frames = unload.unload_frames
        for code, msg, uid in _check_cycle(c):
            fwd.steps.append(StepResult(seq=0, uid=uid, ok=False, errors=[(code, msg)]))
        report.containers.append(fwd)
    return report


def verify_container(c: ContainerInstance) -> ContainerReport:
    fwd = _verify_container_forward(c)
    unload = _verify_container_unload(c)
    fwd.unload_ok = unload.unload_ok
    fwd.unload_errors = unload.unload_errors
    fwd.unload_steps = unload.unload_steps
    fwd.unload_frames = unload.unload_frames
    for code, msg, uid in _check_cycle(c):
        fwd.steps.append(StepResult(seq=0, uid=uid, ok=False, errors=[(code, msg)]))
    return fwd


# --------------------------------------------------------------------------
# error code catalogue (used by tests and UI)
# --------------------------------------------------------------------------

ERROR_CODES = {
    "E101": "外侧货物阻挡内侧货物",
    "E102": "当前排尚未完成",
    "E103": "上层货物缺少支撑",
    "E104": "叉车进入路径被阻挡",
    "E105": "货物放置路径发生碰撞",
    "E106": "货叉无法退出",
    "E107": "叉车无法倒退出柜",
    "E108": "门架举升高度不足",
    "E109": "货物无法通过柜门",
    "E110": "货物超过下层承重",
    "E111": "装载顺序存在循环依赖",
    "E112": "未预留叉车作业空间",
}
