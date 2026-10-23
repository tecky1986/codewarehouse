EPS = 1e-6


def x_overlap(a_x: float, a_dx: float, b_x: float, b_dx: float) -> bool:
    return a_x < b_x + b_dx - EPS and b_x < a_x + a_dx - EPS


def y_overlap(a_y: float, a_dy: float, b_y: float, b_dy: float) -> bool:
    return a_y < b_y + b_dy - EPS and b_y < a_y + a_dy - EPS


def z_touch(a_z: float, a_dz: float, b_z: float) -> bool:
    return abs(a_z + a_dz - b_z) < EPS


def collides(a, b) -> bool:
    """a, b are objects with x,y,z,dx,dy,dz."""
    return (
        x_overlap(a.x, a.dx, b.x, b.dx)
        and y_overlap(a.y, a.dy, b.y, b.dy)
        and a.z < b.z + b.dz - EPS
        and b.z < a.z + a.dz - EPS
    )


def supports(placed, cand) -> list:
    """Items directly under the candidate (their top face == cand bottom)."""
    return [
        p
        for p in placed
        if z_touch(p.z, p.dz, cand.z)
        and x_overlap(p.x, p.dx, cand.x, cand.dx)
        and y_overlap(p.y, p.dy, cand.y, cand.dy)
    ]


def rests_on(placed, cand) -> list:
    """Items directly above the candidate."""
    return [
        p
        for p in placed
        if abs(cand.z + cand.dz - p.z) < EPS
        and x_overlap(p.x, p.dx, cand.x, cand.dx)
        and y_overlap(p.y, p.dy, cand.y, cand.dy)
    ]


def x_range_union(placed_same_pn: list) -> tuple[float, float] | None:
    if not placed_same_pn:
        return None
    lo = min(p.x for p in placed_same_pn)
    hi = max(p.x + p.dx for p in placed_same_pn)
    return lo, hi


def inner_face_min(placed) -> float | None:
    """Min of (x + dx) over placed items; None if empty."""
    if not placed:
        return None
    return min(p.x + p.dx for p in placed)
