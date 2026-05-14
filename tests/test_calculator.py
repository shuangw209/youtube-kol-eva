"""Tests for metric formulas — no network."""

import math

import pytest

from ytkol.calculator import calculate_metrics
from ytkol.models import Sample


def make_samples(specs, commenters=None):
    """specs: list of (views, likes, comments). commenters: optional list of lists."""
    out = []
    commenters = commenters or [[] for _ in specs]
    for i, ((v, l, c), authors) in enumerate(zip(specs, commenters)):
        out.append(
            Sample(
                video_id=f"v{i}",
                url=f"https://www.youtube.com/watch?v=v{i}",
                title=f"video {i}",
                views=v,
                likes=l,
                comments=c,
                commenter_ids=list(authors),
            )
        )
    return out


def test_basic_metrics():
    samples = make_samples([(10000, 100, 20)] * 3)
    m, notes = calculate_metrics(subscribers=10_000, samples=samples, price=500)
    # ER = 120 / 10000 = 0.012
    assert math.isclose(m.er, 0.012, rel_tol=1e-6)
    # View ER = 120 / 10000 = 0.012
    assert math.isclose(m.view_er, 0.012, rel_tol=1e-6)
    # C/L = 20 / 100 = 0.2
    assert math.isclose(m.cl_ratio, 0.2, rel_tol=1e-6)
    # Reach = 10000 / 10000 = 1.0
    assert math.isclose(m.reach_rate, 1.0, rel_tol=1e-6)
    # Stability = 1.0 (all equal)
    assert math.isclose(m.stability, 1.0, rel_tol=1e-6)
    # CPM = 500 / 10 = 50
    assert math.isclose(m.cpm, 50.0, rel_tol=1e-6)


def test_authenticity_all_unique():
    samples = make_samples(
        [(1000, 10, 3)] * 3,
        commenters=[
            ["a", "b", "c"],
            ["d", "e", "f"],
            ["g", "h", "i"],
        ],
    )
    m, _ = calculate_metrics(subscribers=10_000, samples=samples, price=100)
    # 9 total comments, 9 unique authors
    assert math.isclose(m.author_uniqueness, 1.0, rel_tol=1e-6)
    # No author in ≥ 2 videos
    assert m.cross_video_repetition == 0.0


def test_authenticity_full_bot_farm():
    # Same 3 authors comment on every video
    samples = make_samples(
        [(1000, 10, 3)] * 3,
        commenters=[
            ["x", "y", "z"],
            ["x", "y", "z"],
            ["x", "y", "z"],
        ],
    )
    m, _ = calculate_metrics(subscribers=10_000, samples=samples, price=100)
    # 9 comments, 3 unique
    assert math.isclose(m.author_uniqueness, 3 / 9, rel_tol=1e-6)
    # All 9 from cross-video authors
    assert math.isclose(m.cross_video_repetition, 1.0, rel_tol=1e-6)


def test_authenticity_partial_overlap():
    samples = make_samples(
        [(1000, 10, 3)] * 3,
        commenters=[
            ["a", "b", "c"],
            ["a", "d", "e"],   # 'a' overlaps with video 0
            ["a", "f", "g"],   # 'a' overlaps again
        ],
    )
    m, _ = calculate_metrics(subscribers=10_000, samples=samples, price=100)
    # Total = 9, unique = 7 ({a,b,c,d,e,f,g})
    assert math.isclose(m.author_uniqueness, 7 / 9, rel_tol=1e-6)
    # 'a' appears in all 3 → counts as a cross-video author
    # Comments from 'a' = 3 (one per video). 3/9 = 0.333…
    assert math.isclose(m.cross_video_repetition, 3 / 9, rel_tol=1e-6)


def test_no_comments_collected():
    samples = make_samples([(1000, 10, 5)] * 3, commenters=[[], [], []])
    m, notes = calculate_metrics(subscribers=10_000, samples=samples, price=100)
    assert m.author_uniqueness == 0.0
    assert m.cross_video_repetition == 0.0
    assert any("authenticity metrics set to 0" in n for n in notes)


def test_zero_subs_zero_er():
    samples = make_samples([(1000, 10, 1)] * 3)
    m, notes = calculate_metrics(subscribers=0, samples=samples, price=100)
    assert m.er == 0.0
    assert m.reach_rate == 0.0
    assert any("Subscriber count is 0" in n for n in notes)


def test_empty_samples():
    m, notes = calculate_metrics(subscribers=10_000, samples=[], price=100)
    assert m.er == 0.0
    assert m.cpm == 0.0
    assert any("No samples available" in n for n in notes)


def test_stability_calc():
    samples = make_samples([(1000, 10, 1), (5000, 50, 5), (10000, 100, 10)])
    m, _ = calculate_metrics(subscribers=10_000, samples=samples, price=200)
    assert math.isclose(m.stability, 10.0, rel_tol=1e-6)


def test_cpm_calc():
    samples = make_samples([(50000, 100, 10)])
    m, _ = calculate_metrics(subscribers=100_000, samples=samples, price=250)
    # CPM = 250 / 50 = 5
    assert math.isclose(m.cpm, 5.0, rel_tol=1e-6)
