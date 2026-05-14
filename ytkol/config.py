"""Verticals + CPM bands.

The bands describe what CPM (USD per 1000 views) is reasonable for sponsored
content in each vertical. Tweak freely — they're consulted by `verdict.py`
to score the CPM dimension and to compute a 砍价 target.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CpmBands:
    excellent: float  # below this is a steal
    good: float
    acceptable: float  # the user-named upper bound
    expensive: float  # above this triggers 砍价
    # Anything above `expensive * 2` is "absurd" → big score penalty.

    @property
    def absurd(self) -> float:
        return self.expensive * 2


# Defaults the user supplied for tech/AI: CPM ≤ 80 USD acceptable.
VERTICALS: dict[str, CpmBands] = {
    "tech_ai": CpmBands(excellent=25, good=50, acceptable=80, expensive=150),
    "gaming": CpmBands(excellent=8, good=15, acceptable=25, expensive=45),
    "beauty": CpmBands(excellent=15, good=30, acceptable=50, expensive=90),
    "generic": CpmBands(excellent=20, good=40, acceptable=70, expensive=130),
}


def get_bands(vertical: str) -> CpmBands:
    return VERTICALS.get(vertical, VERTICALS["generic"])


# Score weights — they sum to 100.
WEIGHTS = {
    "cpm": 30,
    "er": 20,
    "view_er": 15,
    "authenticity": 25,
    "stability": 10,
}
assert sum(WEIGHTS.values()) == 100
