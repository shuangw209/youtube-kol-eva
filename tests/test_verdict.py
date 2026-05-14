"""Tests for the scoring + verdict engine."""

from ytkol.models import Metrics
from ytkol.verdict import score_and_verdict


def _good_metrics(**overrides) -> Metrics:
    """A baseline 'healthy' metrics object."""
    base = dict(
        er=0.025,  # 2.5%
        view_er=0.04,  # 4%
        cl_ratio=0.04,  # 4%
        reach_rate=1.5,
        stability=2.0,
        cpm=40.0,  # well within tech_ai 'good' band (25-50)
        author_uniqueness=0.92,
        cross_video_repetition=0.05,
    )
    base.update(overrides)
    return Metrics(**base)


def test_healthy_channel_推进合作():
    m = _good_metrics()
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert v.decision == "推进合作"
    assert v.score >= 75
    assert v.red_flags == []


def test_low_sample_red_flag():
    m = _good_metrics()
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=2, vertical="tech_ai"
    )
    assert v.decision == "不合作"
    assert any("样本仅 2" in f for f in v.red_flags)


def test_buy_likes_red_flag():
    m = _good_metrics(cl_ratio=0.005, er=0.0005)  # buy-likes pattern
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert v.decision == "不合作"
    assert any("买赞" in f for f in v.red_flags)


def test_bot_farm_red_flag():
    m = _good_metrics(author_uniqueness=0.20)
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert v.decision == "不合作"
    assert any("水军" in f for f in v.red_flags)


def test_cross_video_repetition_red_flag():
    m = _good_metrics(cross_video_repetition=0.65)
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert v.decision == "不合作"
    assert any("跨视频重复" in f for f in v.red_flags)


def test_unstable_data_red_flag():
    m = _good_metrics(stability=12.0)
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert v.decision == "不合作"
    assert any("波动" in f for f in v.red_flags)


def test_bargain_branch_with_target_price():
    # CPM 110 is in (acceptable=80, expensive=150] for tech_ai → 砍价合作
    # if the rest of the score is healthy enough to land in the 60-74 band.
    m = _good_metrics(cpm=110.0)  # everything else healthy from the baseline
    v = score_and_verdict(
        metrics=m, price=5500, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert v.decision == "砍价合作"
    assert 60 <= v.score <= 74
    # Target should land at the acceptable band ceiling (80 USD CPM)
    assert v.target_cpm == 80
    # 50000 views * 80/1000 = 4000
    assert abs(v.target_price - 4000) < 0.01
    assert "4,000" in v.negotiation_pitch


def test_absurd_cpm_drives_score_low():
    m = _good_metrics(cpm=400.0)  # way above absurd threshold (300)
    v = score_and_verdict(
        metrics=m, price=20000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    # Score should be heavily penalized — likely 暂缓 / 不合作
    assert v.decision in {"暂缓", "不合作", "小单试水"}


def test_score_breakdown_present():
    m = _good_metrics()
    v = score_and_verdict(
        metrics=m, price=2000, avg_views=50_000, sample_size=10, vertical="tech_ai"
    )
    assert "CPM 性价比" in v.score_breakdown
    assert "评论真实性" in v.score_breakdown
    assert sum(int(x.split("/")[0]) for x in v.score_breakdown.values()) == v.score
