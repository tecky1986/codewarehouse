"""Rule checkers. Each checker takes (cand, ctx) and returns a violation
message string, or None when the rule is satisfied.

ctx = CheckContext with:
  .container, .placed (list of Placement/Candidate with x,y,z,dx,dy,dz,item),
  .settings (dict: manual_limit_kg, fork_tine_mm, ...),
  .gap_mm
"""

from dataclasses import dataclass, field

from packing_engine.geometry import EPS, inner_face_min, rests_on, supports, x_range_union, x_overlap, y_overlap
from packing_engine.model import Candidate, effective_loading


@dataclass
class CheckContext:
    settings: dict
    placed: list = field(default_factory=list)

    @property
    def manual_limit(self) -> float:
        return float(self.settings.get("manual_limit_kg", 30))

    @property
    def fork_tine(self) -> float:
        return float(self.settings.get("fork_tine_mm", 1220))

    @property
    def gap(self) -> float:
        return float(self.settings.get("gap_mm", 0))


# -- checkers -----------------------------------------------------------

def chk_bounds(cand: Candidate, ctx: CheckContext):
    c = cand.container
    L, W, H = c.inner_l, c.inner_w, c.inner_h
    if cand.x < -EPS or cand.y < -EPS or cand.z < -EPS:
        return "超出箱内范围"
    if cand.x + cand.dx > L + EPS:
        return "超出箱长"
    if cand.y + cand.dy > W + EPS:
        return "超出箱宽"
    if cand.z + cand.dz > H + EPS:
        return "超出箱高"
    return None


def chk_collision(cand: Candidate, ctx: CheckContext):
    for p in ctx.placed:
        if (
            cand.x < p.x + p.dx - EPS
            and p.x < cand.x + cand.dx - EPS
            and cand.y < p.y + p.dy - EPS
            and p.y < cand.y + cand.dy - EPS
            and cand.z < p.z + p.dz - EPS
            and p.z < cand.z + cand.dz - EPS
        ):
            return "碰撞"
    return None


def chk_payload(cand: Candidate, ctx: CheckContext):
    if cand.container.used_payload + cand.item.gross > cand.container.max_payload + EPS:
        return "超过最大载重"
    return None


def chk_stack_support(cand: Candidate, ctx: CheckContext):
    """Elevated cargo must rest on 1 or 2 rows of equal-height supports.

    A support row split across two containers of the same PN (跨箱压放) is
    treated as one logical row for the two-row limit.
    """
    if cand.z <= EPS:
        return None
    under = supports(ctx.placed, cand)
    if not under:
        return "堆叠缺少支撑"
    ref_h = under[0].dz
    if any(abs(p.dz - ref_h) > EPS for p in under):
        return "被压货物高度不一致"
    rows = _support_rows(under, ctx)
    if rows > 2:
        return "堆叠不得超过两排"
    return None


def _support_rows(under: list, ctx: CheckContext) -> int:
    """Count distinct width-rows among supports.

    A physical row is a (x-span, z-level) band. Two bands belong to the same
    logical row when they share the z-level, overlap in x, and carry the same
    PN (a cross-container split of one PN). The PN 连续 rule enforces a
    contiguity gap on the x-span, so a gap is added here as well.
    """
    bands: list[list] = []
    for p in under:
        found = None
        for b in bands:
            if (
                abs(b[0] - p.z) < EPS
                and b[0] - ctx.gap <= p.x
                and p.x + p.dx <= b[1] + ctx.gap
                and b[2] == p.item.pn
            ):
                found = b
                break
        if found is not None:
            found[0] = min(found[0], p.z)
            found[1] = max(found[1], p.x + p.dx)
        else:
            bands.append([p.z, p.x + p.dx, p.item.pn])
    return len(bands)


def _stack_depth(placed: list, x: float, y: float, dx: float, dy: float) -> int:
    """Count the maximum stacking height (number of layers) at (x, y).

    Walks the support chain upward from the floor, counting each distinct
    z-level that has overlapping cargo at this footprint.
    """
    levels: set[float] = set()
    z = 0.0
    # follow the vertical stack: find all placed items that occupy (x, y)
    # at each z-level, moving upward
    guard = 0
    while guard < 64:
        guard += 1
        found = False
        for p in placed:
            if (
                abs(p.z - z) < EPS
                and x_overlap(x, dx, p.x, p.dx)
                and y_overlap(y, dy, p.y, p.dy)
            ):
                levels.add(round(z, 3))
                z = p.z + p.dz
                found = True
                break
        if not found:
            break
    return len(levels)


def _load_on_support(placed: list, p) -> float:
    """Load resting on top face of placed item p.

    Supports that overlap p fully in the vertical (x/y) projection bear
    their full weight; supports that straddle a container seam (their
    footprint is not fully contained in p's) are split across containers
    and bear only half (跨箱压放按 1/2 计).
    """
    total = 0.0
    for q in placed:
        if abs((q.z - p.z - p.dz)) > EPS:
            continue
        x_split = p.x <= q.x and q.x + q.dx <= p.x + p.dx
        y_split = p.y <= q.y and q.y + q.dy <= p.y + p.dy
        if x_split and y_split:
            total += q.item.gross
        else:
            total += 0.5 * q.item.gross
    return total


def chk_max_stack_layers(cand: Candidate, ctx: CheckContext):
    """Enforce per-item max_stack layers and per-box load capacity.

    Layer limit: the item's own max_stack (None = unlimited).
    Load limit: the supporting box's max_load (None = unlimited). The load
    already resting on each support's top face plus the new item's weight
    must not exceed the capacity.
    """
    item = cand.item
    limit = item.max_stack
    if limit is not None:
        depth = _stack_depth(ctx.placed, cand.x, cand.y, cand.dx, cand.dy)
        if depth + 1 > limit:
            return f"超过最大堆码层数（上限 {limit} 层）"
    under = supports(ctx.placed, cand)
    if under:
        worst = None
        for p in under:
            cap = p.item.max_load
            if cap is None:
                continue
            load = _load_on_support(ctx.placed, p) + cand.item.gross
            if load > cap + EPS:
                if worst is None or load - cap > worst[1]:
                    worst = (p, load - cap, cap)
        if worst:
            cap = worst[2]
            return f"被压货物承重超限（{cap:.0f} kg）"
    return None


def chk_weight_order(cand: Candidate, ctx: CheckContext):
    for p in supports(ctx.placed, cand):
        if p.item.gross < cand.item.gross - EPS:
            return "轻重堆叠约束不满足"
    for p in rests_on(ctx.placed, cand):
        if cand.item.gross < p.item.gross - EPS:
            return "轻重堆叠约束不满足"
    return None


def chk_crush(cand: Candidate, ctx: CheckContext):
    for p in supports(ctx.placed, cand):
        if p.item.crush_sensitive:
            return "易压约束不满足"
    return None


def chk_same_type_stack(cand: Candidate, ctx: CheckContext):
    for p in supports(ctx.placed, cand):
        if cand.item.same_type_stack or p.item.same_type_stack:
            if cand.item.cargo_type != p.item.cargo_type:
                return "同种堆叠约束不满足"
    for p in rests_on(ctx.placed, cand):
        if cand.item.same_type_stack or p.item.same_type_stack:
            if cand.item.cargo_type != p.item.cargo_type:
                return "同种堆叠约束不满足"
    return None


def chk_fork_tine(cand: Candidate, ctx: CheckContext):
    if effective_loading(cand.item, ctx.manual_limit) == "forklift":
        if cand.dx > ctx.fork_tine + EPS:
            return "铲齿长度约束不满足"
    return None


def chk_manual_limit(cand: Candidate, ctx: CheckContext):
    if cand.item.gross > ctx.manual_limit + EPS and cand.item.loading != "forklift":
        return "人工重量上限不满足"
    return None


def chk_pn_continuous(cand: Candidate, ctx: CheckContext):
    pn = cand.item.pn
    if not pn:
        return None
    same = [p for p in ctx.placed if p.item.pn == pn]
    if not same:
        return None
    lo, hi = x_range_union(same)
    lo, hi = lo - ctx.gap, hi + ctx.gap
    if cand.x > hi + EPS:
        return "PN 连续性不满足"
    if cand.x + cand.dx < lo - EPS:
        return "PN 连续性不满足"
    return None


def chk_inside_out(cand: Candidate, ctx: CheckContext):
    earlier = [p for p in ctx.placed if p.load_seq < cand.load_seq]
    if not earlier:
        return None
    limit = inner_face_min(earlier)
    if cand.x + cand.dx > limit + EPS:
        return "由内向外顺序不满足"
    return None


CHECKERS = {
    "bounds": chk_bounds,
    "collision": chk_collision,
    "payload": chk_payload,
    "stack_support": chk_stack_support,
    "max_stack_layers": chk_max_stack_layers,
    "weight_order": chk_weight_order,
    "crush": chk_crush,
    "same_type_stack": chk_same_type_stack,
    "fork_tine": chk_fork_tine,
    "manual_limit": chk_manual_limit,
    "pn_continuous": chk_pn_continuous,
    "inside_out": chk_inside_out,
}


def run_checkers(
    cand: Candidate,
    ctx: CheckContext,
    enabled_rules: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Return [(rule, reason)] for enabled rules that fail.

    The hard rules (bounds/collision/payload) are always enforced regardless
    of the enabled list; the business rules follow the enabled list.
    """
    hard = ["bounds", "collision", "payload", "stack_support"]
    if enabled_rules is None:
        soft = [r for r in CHECKERS if r not in hard]
    else:
        soft = [r for r in enabled_rules if r not in hard and r in CHECKERS]
    wanted = hard + soft
    out = []
    for name in wanted:
        reason = CHECKERS[name](cand, ctx)
        if reason:
            out.append((name, reason))
    return out
