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

    ordered: list[CargoItem] = []
    for group in chains.values():
        ordered.extend(heavy_first(group))
    ordered.extend(heavy_first(rest))
    return ordered


def group_total(items: list[CargoItem]) -> tuple[float, float]:
    vol = sum(i.volume_m3() for i in items)
    gross = sum(i.gross for i in items)
    return vol, gross
