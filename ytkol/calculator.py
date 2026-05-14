"""Metric calculation: 6 core + author_uniqueness + cross_video_repetition."""

from __future__ import annotations

from collections import Counter
from statistics import mean

from ytkol.models import Metrics, Sample


def _safe_div(num: float, denom: float) -> float:
    if denom == 0:
        return 0.0
    return num / denom


def calculate_metrics(
    *,
    subscribers: int,
    samples: list[Sample],
    price: float,
) -> tuple[Metrics, list[str]]:
    """Compute Metrics from raw samples. Returns (metrics, notes)."""
    notes: list[str] = []

    if not samples:
        notes.append("No samples available — every metric will be 0.")
        return Metrics(), notes
    if len(samples) < 3:
        notes.append(
            f"Only {len(samples)} sample(s). Metrics may be noisy; aim for ≥ 5 for "
            "a meaningful read."
        )
    if subscribers <= 0:
        notes.append(
            "Subscriber count is 0 or hidden — ER and Reach Rate will be 0."
        )

    avg_views = mean(s.views for s in samples)
    avg_likes = mean(s.likes for s in samples)
    avg_comments = mean(s.comments for s in samples)
    total_engagement_avg = avg_likes + avg_comments

    nonzero_views = [s.views for s in samples if s.views > 0]
    if len(nonzero_views) >= 2:
        stability = max(nonzero_views) / min(nonzero_views)
    elif len(nonzero_views) == 1:
        stability = 1.0
        notes.append(
            "Only one sample had non-zero views — stability is not meaningful."
        )
    else:
        stability = 0.0
        notes.append("All samples had zero views — most metrics will be 0.")

    if avg_views == 0:
        notes.append("Average views is 0 — View ER / Reach Rate / CPM cannot be computed.")
    if avg_likes == 0:
        notes.append("Average likes is 0 — C/L Ratio set to 0.")

    # Authenticity: unique vs total commenters
    total_comments = sum(len(s.commenter_ids) for s in samples)
    if total_comments == 0:
        notes.append(
            "No top-level comments collected — authenticity metrics set to 0. "
            "Comments may be disabled on these videos, or quota ran out."
        )
        author_uniqueness = 0.0
        cross_video_repetition = 0.0
    else:
        all_authors: Counter = Counter()
        per_video_authors: list[set[str]] = []
        for s in samples:
            seen = set(s.commenter_ids)  # de-dup within a video first
            per_video_authors.append(seen)
            all_authors.update(seen)

        unique_authors = len(all_authors)
        author_uniqueness = unique_authors / total_comments

        # Cross-video: fraction of comments that came from authors who appear
        # in at least 2 videos in the sample. Healthy fans show up sometimes;
        # bot farms saturate everywhere.
        cross_authors = {a for a, c in all_authors.items() if c >= 2}
        cross_count = sum(
            1 for s in samples for cid in s.commenter_ids if cid in cross_authors
        )
        cross_video_repetition = cross_count / total_comments

    metrics = Metrics(
        er=_safe_div(total_engagement_avg, subscribers),
        view_er=_safe_div(total_engagement_avg, avg_views),
        cl_ratio=_safe_div(avg_comments, avg_likes),
        reach_rate=_safe_div(avg_views, subscribers),
        stability=stability,
        cpm=_safe_div(price, avg_views / 1000.0) if avg_views > 0 else 0.0,
        author_uniqueness=author_uniqueness,
        cross_video_repetition=cross_video_repetition,
    )
    return metrics, notes
