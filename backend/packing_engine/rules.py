"""Rule checkers. Each checker takes (cand, ctx) and returns a violation
message string, or None when the rule is satisfied.

ctx = CheckContext with:
  .container, .placed (list of Placement/Candidate with x,y,z,dx,dy,dz,item),
  .settings (dict: manual_limit_kg, fork_tine_mm, ...),
  .gap_mm
"""

from dataclasses import dataclass, field

from packing_engine.geometry import EPS, inner_face_min, rests_on, supports, x_range_union
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
    hard = ["bounds", "collision", "payload"]
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
