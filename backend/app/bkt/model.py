from dataclasses import dataclass, field


@dataclass
class BKTParams:
    p_l0: float = 0.50
    p_t: float = 0.20
    p_g: float = 0.15
    p_s: float = 0.10


@dataclass
class BKTState:
    params: BKTParams = field(default_factory=BKTParams)
    p_know: float = 0.50
