"""Build CargoItems + containers from DB rows for computation."""

import re
from packing_engine.model import CargoItem, ContainerInstance, Plan

import json

from packing_engine.freemix import search as _freemix_search


def _pn_regex(pn: str) -> re.Pattern:
    """Compile PN pattern: ? matches any number of chars (.*);
    each # matches exactly one char."""
    parts: list[str] = []
    i = 0
    while i < len(pn):
        c = pn[i]
        if c == "?":
            while i < len(pn) and pn[i] == "?":
                i += 1
            parts.append(".*")
        elif c == "#":
            j = i
            while j < len(pn) and pn[j] == "#":
                j += 1
            parts.append("." * (j - i))
            i = j
        else:
            j = i
            while j < len(pn) and pn[j] not in ("?", "#"):
                j += 1
            parts.append(re.escape(pn[i:j]))
            i = j
    return re.compile("".join(parts) + "$")


def _match_pn(pn: str, pattern: str) -> bool:
    """Return True when *pn* matches *pattern*.
    ? = any number of chars; # = exactly one char."""
    if "?" not in pattern and "#" not in pattern:
        return pn == pattern
    return bool(_pn_regex(pattern).match(pn))


def freemix(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules,
    site_groups,
    reporter,
    locks: dict | None = None,
) -> Plan:
    """Freemix algorithm entry registered as a solver.

    `containers` encodes the catalog: one prototype instance per type_code.
    `locks` (type_lock / qty_lock / max_qty) bound the search (R19 AC4-6/12).
    An infeasible combination (R19 AC10) or a best plan with unassigned
    items yields an empty plan: everything unassigned, reason E_NO_FEASIBLE.
    """
    # dedupe catalog prototypes by type_code
    catalog: dict[str, ContainerInstance] = {}
    for c in containers:
        catalog.setdefault(c.type_code, c)
    plan, error, timed_out = _freemix_search(
        items, catalog, locks or {}, settings, enabled_rules, site_groups, reporter
    )
    if plan is not None:
        return plan
    return Plan(
        algorithm="freemix",
        containers=[],
        unassigned=list(items),
        error=error,
        timed_out=timed_out,
    )

def items_from_rows(rows: list[dict], packages: list[dict] | None = None, manual_limit_kg: float = 30.0) -> list[CargoItem]:
    """Build engine items from import_row dicts.

    `packages` (optional) can provide the same fields as an enabled
    package_master row, keyed by pn / packmatls; import rows already have
    filled dims/weights from the import service, so `packages` is only
    used to fill rule attributes (crush, same_type_stack, rotatable, ...)
    when the source row did not carry them.
    """
    pkg_by_pn: dict[str, dict] = {}
    pkg_by_name: dict[str, dict] = {}
    pkg_patterns: list[tuple[str, dict]] = []  # (pattern_pn, master)

    for p in packages or []:
        pn_p = p.get("pn")
        if pn_p:
            if "?" in pn_p or "#" in pn_p:
                pkg_patterns.append((pn_p, p))
            else:
                pkg_by_pn.setdefault(pn_p, p)
        key = p.get("package_type") or p.get("name")
        if key:
            pkg_by_name.setdefault(key, p)

    def _find_master(pn: str | None, pack: str | None) -> dict | None:
        if pn:
            m = pkg_by_pn.get(pn)
            if m is not None:
                return m
            for pat, p in pkg_patterns:
                if _match_pn(pn, pat):
                    return p
        if pack:
            return pkg_by_name.get(pack)
        return None

    out: list[CargoItem] = []
    for r in rows:
        if not r.get("complete", True):
            continue
        pn = r.get("k_pn")
        pack = r.get("g_packmatls")
        master = _find_master(pn, pack)

        def _d(key, default=0.0):
            v = r.get(key)
            return float(v) if v is not None else default

        item = CargoItem(
            uid=f"r{r.get('id')}",
            row_no=r.get("row_no"),
            pn=pn,
            packmatls=pack,
            cargo_type=(master or {}).get("cargo_type"),
            l=_d("b_len"),
            w=_d("c_wid"),
            h=_d("d_hgt"),
            tare=_d("h_tare"),
            net=_d("i_net"),
            gross=_d("j_gross"),
            volume=(float(r["e_cbm"]) if r.get("e_cbm") is not None else None),
            rotatable=bool((master or {}).get("rotatable", 1)),
            crush_sensitive=bool((master or {}).get("crush_sensitive", 0)),
            same_type_stack=bool((master or {}).get("same_type_stack", 0)),
            loading=str((master or {}).get("default_loading") or "manual"),
            max_stack=(master or {}).get("max_stack"),
            max_load=(master or {}).get("max_load"),
            site=r.get("m_site"),
            outcase=r.get("f_outcase"),
            source_flag=r.get("source_flag") or "table",
        )
        if item.gross > manual_limit_kg:
            item.loading = "forklift"
        out.append(item)
    return out


def fixed_containers(
    type_code: str,
    count: int,
    catalog: dict[str, dict],
) -> list[ContainerInstance]:
    row = catalog.get(type_code)
    if not row:
        raise ValueError(f"container type not found: {type_code}")
    out = []
    for i in range(1, count + 1):
        out.append(
            ContainerInstance(
                type_code=type_code,
                seq_no=i,
                label=f"{type_code}-{i}",
                inner_l=int(row["inner_l"]),
                inner_w=int(row["inner_w"]),
                inner_h=int(row["inner_h"]),
                max_payload=float(row["max_payload"]),
                volume_m3=float(row.get("volume") or 0),
                freight_price=float(row.get("freight_price") or 0),
                door_w=row.get("door_w"),
                door_h=row.get("door_h"),
            )
        )
    return out


def fixed_containers_multi(
    specs: list[tuple[str, int]],
    catalog: dict[str, dict],
) -> list[ContainerInstance]:
    """Build container instances from a list of (type_code, count) specs.

    Same type appears with per-type sequence numbers (20GP-1, 20GP-2, 40GP-1...).
    """
    out: list[ContainerInstance] = []
    counters: dict[str, int] = {}
    for type_code, count in specs:
        row = catalog.get(type_code)
        if not row:
            raise ValueError(f"container type not found: {type_code}")
        for _ in range(int(count)):
            counters[type_code] = counters.get(type_code, 0) + 1
            out.append(
                ContainerInstance(
                    type_code=type_code,
                    seq_no=counters[type_code],
                    label=f"{type_code}-{counters[type_code]}",
                    inner_l=int(row["inner_l"]),
                    inner_w=int(row["inner_w"]),
                    inner_h=int(row["inner_h"]),
                    max_payload=float(row["max_payload"]),
                    volume_m3=float(row.get("volume") or 0),
                    freight_price=float(row.get("freight_price") or 0),
                    door_w=row.get("door_w"),
                    door_h=row.get("door_h"),
                )
            )
    return out
