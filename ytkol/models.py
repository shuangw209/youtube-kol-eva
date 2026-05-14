"""Data classes used across the package."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Sample:
    """Stats for one YouTube video."""

    video_id: str = ""
    url: str = ""
    title: str = ""
    published_at: str = ""  # ISO-8601
    duration_seconds: int = 0
    is_short: bool = False
    views: int = 0
    likes: int = 0
    comments: int = 0
    # Set of unique top-level commenter authorChannelIds collected for this video.
    commenter_ids: list[str] = field(default_factory=list)

    @property
    def total_engagement(self) -> int:
        return self.likes + self.comments


@dataclass
class Metrics:
    """The 6 core metrics + 2 authenticity metrics."""

    er: float = 0.0  # (likes + comments) / subscribers
    view_er: float = 0.0  # (likes + comments) / avg_views
    cl_ratio: float = 0.0  # comments / likes
    reach_rate: float = 0.0  # avg_views / subscribers
    stability: float = 0.0  # max_views / min_views
    cpm: float = 0.0  # price / (avg_views / 1000)
    # Authenticity (new):
    author_uniqueness: float = 0.0  # unique_authors / total_comments
    cross_video_repetition: float = 0.0  # comments_from_authors_in_>=2_vids / total


@dataclass
class Verdict:
    """Recommendation produced by the scoring engine."""

    decision: str = ""  # 推进合作 / 砍价合作 / 小单试水 / 暂缓 / 不合作
    score: int = 0  # 0–100
    score_breakdown: dict = field(default_factory=dict)
    red_flags: list[str] = field(default_factory=list)
    target_price: float | None = None  # for 砍价合作
    target_cpm: float | None = None
    negotiation_pitch: str = ""  # one-liner the user can copy-paste
    explanation: list[str] = field(default_factory=list)  # human-readable bullets


@dataclass
class Report:
    """Top-level result. Serializable to JSON via asdict()."""

    handle: str
    channel_id: str
    channel_title: str
    channel_url: str
    subscribers: int
    price: float
    currency: str
    vertical: str
    sample_size: int
    avg_views: float
    avg_likes: float
    avg_comments: float
    total_comments_collected: int
    unique_commenters: int
    metrics: Metrics
    verdict: Verdict
    samples: list[Sample] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        # Strip commenter_ids from samples in the serialized form — they're
        # only used internally for authenticity calculation, and would bloat
        # the JSON output (potentially with PII implications).
        d = asdict(self)
        for s in d.get("samples", []):
            s.pop("commenter_ids", None)
        return d
