"""Large neighborhood search local optimizer for packed plans."""

import random
from dataclasses import replace

from packing_engine.groups import order_items
from packing_engine.model import Candidate, CargoItem, ContainerInstance, Plan
from packing_engine.place import ProgressReporter, _finish_plan, dblf
from packing_engine.rules import CheckContext, run_checkers


def _orientations(item: CargoItem):
    if item.rotatable:
        return [(item.l, item.w, item.h), (item.w, item.l, item.h)]
    return [(item.l, item.w, item.h)]


def _valid_candidates(item: CargoItem, container: ContainerInstance, placed: list, settings: dict, enabled_rules: list, sample_size: int | None = None) -> list[Candidate]:
    out: list[Candidate] = []
    rng = random.Random(0)
    if not placed:
        check_ctx = CheckContext(settings=settings, placed=[])
        for (dx, dy, dz) in _orientations(item):
            for x in (0.0, max(0.0, container.inner_l - dx)):
                for y in (0.0, container.inner_w - dy):
                    for z in (0.0, container.max_z - dz):
                        if x + dx > container.inner_l + 1e-9 or y + dy > container.inner_w + 1e-9 or z + dz > container.max_z + 1e-9:
                            continue
                        cand = Candidate(item=item, container=container, x=x, y=y, z=z, dx=dx, dy=dy, dz=dz, load_seq=len(placed) + 1)
                        if not run_checkers(cand, check_ctx, enabled_rules):
                            out.append(cand)
        return out

    points: set[tuple[float, float, float]] = set()
    for p in placed:
        points.add((float(container.inner_l), p.y + p.dy, p.z))
        points.add((float(container.inner_l), p.y, p.z + p.dz))
        points.add((p.x, p.y, p.z))
        points.add((p.x + p.dx, p.y, p.z))
    points.add((float(container.inner_l), 0.0, 0.0))
    points.add((0.0, 0.0, 0.0))
    points_list = sorted(points, key=lambda p: (-p[0], p[2], p[1]))
    if sample_size is not None:
        if len(points_list) > sample_size:
            points_list = rng.sample(points_list, sample_size)
    check_ctx = CheckContext(settings=settings, placed=placed)
    for cap, y, z in points_list:
        if cap > container.inner_l + 1e-9 or y > container.inner_w + 1e-9 or z > container.max_z + 1e-9:
            continue
        for (dx, dy, dz) in _orientations(item):
            x = cap - dx
            if x < -1e-9 or dy > container.inner_w - y + 1e-9 or dz > container.max_z - z + 1e-9:
                continue
            cand = Candidate(item=item, container=container, x=max(0.0, x), y=y, z=z, dx=dx, dy=dy, dz=dz, load_seq=len(placed) + 1)
            if not run_checkers(cand, check_ctx, enabled_rules):
                out.append(cand)
    return out


def _score_key(plan: Plan) -> tuple:
    placed_count = sum(len(c.placed) for c in plan.containers)
    vol_used = sum(c.used_volume for c in plan.containers)
    vol_cap = sum(c.volume_m3 for c in plan.containers if c.placed)
    vol_util = vol_used / vol_cap if vol_cap > 0 else 0.0
    unassigned_count = len(plan.unassigned)
    containers_used = sum(1 for c in plan.containers if c.placed)
    return (-placed_count, -vol_util, containers_used, unassigned_count)


def _copy_plan(plan: Plan, containers: list[ContainerInstance], unassigned: list[CargoItem]) -> Plan:
    copied = Plan(algorithm=plan.algorithm, containers=containers, unassigned=unassigned, error=plan.error, mode=plan.mode)
    copied.kpi = dict(plan.kpi or {})
    copied.elapsed_s = plan.elapsed_s
    copied.timed_out = plan.timed_out
    for c in containers:
        for p in c.placed:
            p.container = c
    return copied


def _remove_neighborhood(containers: list[ContainerInstance], neighborhood_size: int, rng: random.Random) -> tuple[list[CargoItem], set[int]]:
    removable: list[tuple[int, int]] = []
    for ci, c in enumerate(containers):
        for pi in range(len(c.placed)):
            removable.append((ci, pi))
    rng.shuffle(removable)
    removed_uids: set[str] = set()
    selected: list[tuple[int, int, CargoItem]] = []
    for ci, pi in removable:
        cand = containers[ci].placed[pi]
        if cand.item.uid in removed_uids:
            continue
        selected.append((ci, pi, cand.item))
        removed_uids.add(cand.item.uid)
        if len(selected) >= neighborhood_size:
            break
    removed_containers = {ci for ci, _, _ in selected}
    for ci, _, _ in selected:
        containers[ci].placed = [p for p in containers[ci].placed if p.item.uid not in removed_uids]
    return [item for _, _, item in selected], removed_containers


def _try_reinsert(items: list[CargoItem], containers: list[ContainerInstance], settings: dict, enabled_rules: list, containers_used: set[int]) -> tuple[int, list[CargoItem]]:
    unassigned: list[CargoItem] = []
    ordered = order_items(items)
    placed_count = 0
    for item in ordered:
        ok = False
        container_indices = sorted(containers_used) if containers_used else list(range(len(containers)))
        for ci in container_indices:
            c = containers[ci]
            if not _fits_payload(c, item):
                continue
            candidates = _valid_candidates(item, c, c.placed, settings, enabled_rules, sample_size=int(settings.get("lns_candidate_sample", 48)))
            if not candidates:
                continue
            best = min(candidates, key=lambda cand: (-(cand.x + cand.dx), cand.z, cand.y, cand.x))
            best = replace(best, load_seq=len(c.placed) + 1)
            c.placed.append(best)
            ok = True
            placed_count += 1
            break
        if not ok:
            unassigned.append(item)
    return placed_count, unassigned


def _fits_payload(c: ContainerInstance, item: CargoItem) -> bool:
    return c.remaining_payload + 1e-6 >= item.gross


def lns(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    seed_containers = [replace(c, placed=list()) for c in containers]
    seed = dblf(
        list(items),
        seed_containers,
        settings,
        enabled_rules,
        site_groups,
        reporter,
    )

    base = Plan(algorithm="lns", containers=[replace(c, placed=list(c.placed)) for c in seed_containers], unassigned=list(seed.unassigned))
    best = _copy_plan(base, [replace(c, placed=list(c.placed)) for c in base.containers], list(base.unassigned))
    best_key = _score_key(best)
    placed_total = sum(len(c.placed) for c in best.containers)
    neighborhood_size = int(settings.get("lns_neighborhood", max(1, min(8, placed_total // 10 or 1))))
    rng = random.Random(int(settings.get("lns_seed", 0)) or None)
    reporter.tick()

    while not reporter.timed_out:
        trial = _copy_plan(best, [replace(c, placed=list(c.placed)) for c in best.containers], list(best.unassigned))
        neighbor, removed_ids = _remove_neighborhood(trial.containers, neighborhood_size, rng)
        if not neighbor:
            break
        _, placed_unassigned = _try_reinsert(neighbor, trial.containers, settings, enabled_rules, removed_ids)
        trial.unassigned.extend(placed_unassigned)
        trial_key = _score_key(trial)
        if trial_key < best_key:
            best = trial
            best_key = trial_key
        reporter.tick()

    _finish_plan("lns", best.containers, best.unassigned, reporter.timed_out)
    return best
