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
    """Largest cargo families first; same PN stays contiguous within a family.

    Grouping by cargo_type / packmatls keeps identical large boxes together
    so they can claim a wall before smaller boxes fill the leftover strip.
    Within a family, PN chains stay contiguous (R8), heaviest first.
    """

    def family_key(item: CargoItem) -> str:
        return item.cargo_type or item.packmatls or ""

    def heavy_first(group: list[CargoItem]) -> list[CargoItem]:
        return sorted(group, key=lambda i: (-i.gross, i.uid))

    def pn_block(group: list[CargoItem]) -> list[CargoItem]:
        chains: "OrderedDict[str, list[CargoItem]]" = OrderedDict()
        rest: list[CargoItem] = []
        for it in group:
            if it.pn:
                chains.setdefault(it.pn, []).append(it)
            else:
                rest.append(it)
        ordered: list[CargoItem] = []
        for chain in chains.values():
            ordered.extend(heavy_first(chain))
        ordered.extend(heavy_first(rest))
        return ordered

    by_type: "OrderedDict[str, list[CargoItem]]" = OrderedDict()
    for it in items:
        by_type.setdefault(family_key(it), []).append(it)
    ordered: list[CargoItem] = []
    for _, group in sorted(by_type.items(), key=lambda kv: -sum(i.volume_m3() for i in kv[1])):
        ordered.extend(pn_block(group))
    return ordered


def group_total(items: list[CargoItem]) -> tuple[float, float]:
    vol = sum(i.volume_m3() for i in items)
    gross = sum(i.gross for i in items)
    return vol, gross
