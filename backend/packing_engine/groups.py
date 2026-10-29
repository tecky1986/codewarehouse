from collections import OrderedDict

from packing_engine.model import CargoItem


def site_together_groups(items: list[CargoItem], site_groups: list[dict]) -> dict[str, list[CargoItem]]:
    """site -> items, only for sites marked together."""
    together = {g.get("site") for g in (site_groups or []) if g.get("together")}
    groups: dict[str, list[CargoItem]] = {}
    for it in items:
        if it.site in together:
            groups.setdefault(it.site, []).append(it)
    return {k: v for k, v in groups.items() if k}


def site_separate_sites(items: list[CargoItem], site_groups: list[dict]) -> set[str]:
    sep = {g.get("site") for g in (site_groups or []) if g.get("separate")}
    return {it.site for it in items if it.site in sep} & sep


def order_items(items: list[CargoItem]) -> list[CargoItem]:
    """PN chains first (heaviest first within a chain), then remaining items.

    Same PN stays contiguous so it can fill the current container and
    continue in the next one (R8).

    The no-PN remainder is grouped by cargo_type so identical large boxes
    can wall-fill the current container before the algorithm moves on to
    smaller boxes; this prevents a 175-row real dataset from leaving
    30+ items unassigned just because two boxes of the same type got
    split apart by smaller interleaved items.
    """
    chains: "OrderedDict[str, list[CargoItem]]" = OrderedDict()
    rest: list[CargoItem] = []
    for it in items:
        if it.pn:
            chains.setdefault(it.pn, []).append(it)
        else:
            rest.append(it)

    def heavy_first(group: list[CargoItem]) -> list[CargoItem]:
        return sorted(group, key=lambda i: (-i.gross, i.uid))

    def no_pn_block(group: list[CargoItem]) -> list[CargoItem]:
        """Group by cargo_type so same-type boxes stay contiguous."""
        by_type: "OrderedDict[str, list[CargoItem]]" = OrderedDict()
        for it in group:
            by_type.setdefault(it.cargo_type, []).append(it)
        # Order types by descending total volume, so the largest family
        # is placed first to maximize wall-fill opportunities.
        ordered: list[CargoItem] = []
        for cto in sorted(by_type.items(), key=lambda kv: -sum(i.volume_m3() for i in kv[1])):
            ordered.extend(heavy_first(cto[1]))
        return ordered

    ordered: list[CargoItem] = []
    for group in chains.values():
        ordered.extend(heavy_first(group))
    ordered.extend(no_pn_block(rest))
    return ordered


def group_total(items: list[CargoItem]) -> tuple[float, float]:
    vol = sum(i.volume_m3() for i in items)
    gross = sum(i.gross for i in items)
    return vol, gross
