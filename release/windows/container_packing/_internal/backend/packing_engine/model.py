from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CargoItem:
    uid: str
    pn: Optional[str]
    packmatls: Optional[str]
    cargo_type: Optional[str]
    l: float
    w: float
    h: float
    tare: float = 0.0
    net: float = 0.0
    gross: float = 0.0
    volume: Optional[float] = None  # m3, fallback l*w*h/1e9
    rotatable: bool = True
    crush_sensitive: bool = False
    same_type_stack: bool = False
    loading: str = "manual"  # manual | forklift (effective after normalize)
    max_stack: Optional[int] = None
    site: Optional[str] = None
    outcase: Optional[str] = None
    row_no: Optional[int] = None
    source_flag: str = "table"

    @property
    def dims_m3(self) -> float:
        if self.volume is not None:
            return self.volume
        return self.l * self.w * self.h / 1_000_000_000

    def volume_m3(self) -> float:
        return self.dims_m3


@dataclass
class ContainerInstance:
    type_code: str
    seq_no: int
    label: str
    inner_l: int
    inner_w: int
    inner_h: int
    max_payload: float
    volume_m3: float
    placed: list = field(default_factory=list)

    @property
    def used_volume(self) -> float:
        return sum(p.item.volume_m3() for p in self.placed)

    @property
    def used_payload(self) -> float:
        return sum(p.item.gross for p in self.placed)

    @property
    def remaining_volume(self) -> float:
        return self.volume_m3 - self.used_volume

    @property
    def remaining_payload(self) -> float:
        return self.max_payload - self.used_payload


@dataclass
class Candidate:
    item: CargoItem
    container: ContainerInstance
    x: float
    y: float
    z: float
    dx: float
    dy: float
    dz: float
    load_seq: int = 0
    degraded_rules: list = field(default_factory=list)


@dataclass
class Plan:
    algorithm: str = "dblf"
    containers: list = field(default_factory=list)
    unassigned: list = field(default_factory=list)
    kpi: dict = field(default_factory=dict)
    elapsed_s: float = 0.0
    timed_out: bool = False
    error: str | None = None
    mode: str = "fixed"


def effective_loading(item: CargoItem, manual_limit_kg: float) -> str:
    if item.gross > manual_limit_kg:
        return "forklift"
    return item.loading
