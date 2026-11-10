"""Additional placement strategies.

``extreme_point`` runs over the same maximal-free-space core as the other
space-based strategies (see ``packing_engine.place._pack_spaces``) but orders
candidate spaces by their deepest free corner — the extreme point farthest
from the door, i.e. flush against the inner end wall.  Like ``dblf`` it keeps
the single-container fill dense instead of abandoning a container after one
thin layer, the defect the old cap-point model had.
"""

from packing_engine.model import Candidate, CargoItem, ContainerInstance, Plan
from packing_engine.place import ProgressReporter, _pack_spaces, register


def extreme_point(
    items: list[CargoItem],
    containers: list[ContainerInstance],
    settings: dict,
    enabled_rules: list,
    site_groups: list,
    reporter: ProgressReporter,
) -> Plan:
    def score(space, cand: Candidate) -> tuple:
        # extreme point = the deepest free corner: place items flush against
        # the inner end wall (maximize x+dx) before moving toward the door,
        # then build up in z, then along y; on ties take the tightest space.
        # This keeps the single-container fill dense instead of front-stacking.
        return (-(cand.x + cand.dx), cand.z, cand.y, space.volume())

    return _pack_spaces(
        "extreme_point", items, containers, settings, enabled_rules, site_groups, reporter, score
    )


# ---------------------------------------------------------------------------
# Wall build and guillotine strategies were retired; the active core set now
# uses layer-based packing, maximal spaces, extreme points, bottom-left-back
# candidate ordering, and LNS local improvement.
# ---------------------------------------------------------------------------


from packing_engine.lns import lns as _lns_fn

register("extreme_point", extreme_point)
register("lns", _lns_fn)
