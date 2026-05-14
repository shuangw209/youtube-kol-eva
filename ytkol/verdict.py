"""Scoring + recommendation engine.

Inputs: Metrics + price + vertical → Verdict.

Two-layer logic:
  1. Hard red flags (auto-降级):
       - C/L Ratio < 1% AND ER < 0.1%   → 买赞模式
       - author_uniqueness < 0.40       → 重度水军
       - cross_video_repetition > 0.50  → 同一批人刷遍所有视频
       - Stability > 10x                → 数据不稳定
       - sample_size < 3                → 样本不足

  2. Score (0–100), summed across 5 dimensions (weights in config.py):
       - CPM 性价比 (30)
       - ER 互动率 (20)
       - View ER 互动质量 (15)
       - 评论真实性 (25) — author_uniqueness + cross_video_repetition + C/L
       - Stability 稳定性 (10)

Decision thresholds:
       score ≥ 75 + no red flags                    → 推进合作
       score 60–74 + CPM ≤ acceptable               → 推进合作
       score 60–74 + CPM in (acceptable, expensive] → 推进合作但砍价
       score 45–59                                  → 小单试水
       score 30–44                                  → 暂缓
       score < 30 OR any red flag                   → 不合作
"""

from __future__ import annotations

from ytkol.config import WEIGHTS, get_bands
from ytkol.models import Metrics, Verdict


def _score_cpm(cpm: float, vertical: str) -> tuple[int, str]:
    bands = get_bands(vertical)
    w = WEIGHTS["cpm"]
    if cpm <= 0:
        return (0, "CPM 无法计算（曝光数据缺失）")
    if cpm < bands.excellent:
        return (w, f"CPM {cpm:.2f} 远低于 {bands.excellent} 的优秀线，性价比极高")
    if cpm < bands.good:
        return (int(w * 0.83), f"CPM {cpm:.2f} 在 {bands.excellent}–{bands.good} 区间，划算")
    if cpm <= bands.acceptable:
        return (int(w * 0.60), f"CPM {cpm:.2f} 在可接受区间内（≤ {bands.acceptable}）")
    if cpm <= bands.expensive:
        return (int(w * 0.27), f"CPM {cpm:.2f} 偏高，触发砍价建议")
    if cpm <= bands.absurd:
        return (int(w * 0.10), f"CPM {cpm:.2f} 远超合理区间")
    return (0, f"CPM {cpm:.2f} 离谱（行业上限的 2 倍以上）")


def _score_er(er: float) -> tuple[int, str]:
    w = WEIGHTS["er"]
    pct = er * 100
    if pct >= 5:
        return (w, f"ER {pct:.2f}% 优秀")
    if pct >= 2:
        return (int(w * 0.75), f"ER {pct:.2f}% 良好")
    if pct >= 1:
        return (int(w * 0.50), f"ER {pct:.2f}% 一般")
    if pct >= 0.5:
        return (int(w * 0.25), f"ER {pct:.2f}% 偏低")
    return (0, f"ER {pct:.2f}% 太低")


def _score_view_er(view_er: float) -> tuple[int, str]:
    w = WEIGHTS["view_er"]
    pct = view_er * 100
    if pct >= 5:
        return (w, f"View ER {pct:.2f}% 优秀")
    if pct >= 2:
        return (int(w * 0.80), f"View ER {pct:.2f}% 良好")
    if pct >= 1:
        return (int(w * 0.53), f"View ER {pct:.2f}% 一般")
    return (int(w * 0.20), f"View ER {pct:.2f}% 偏低")


def _score_authenticity(metrics: Metrics) -> tuple[int, str]:
    w = WEIGHTS["authenticity"]
    pts = 0.0
    notes: list[str] = []

    # Sub-component 1: author_uniqueness (12 pts)
    if metrics.author_uniqueness >= 0.85:
        pts += 12
        notes.append(f"评论人独立度高（{metrics.author_uniqueness:.0%}）")
    elif metrics.author_uniqueness >= 0.70:
        pts += 9
        notes.append(f"评论人独立度尚可（{metrics.author_uniqueness:.0%}）")
    elif metrics.author_uniqueness >= 0.50:
        pts += 5
        notes.append(f"评论人独立度偏低（{metrics.author_uniqueness:.0%}）")
    elif metrics.author_uniqueness > 0:
        pts += 1
        notes.append(f"评论人独立度很低（{metrics.author_uniqueness:.0%}）—— 水军嫌疑")
    else:
        notes.append("无评论数据")

    # Sub-component 2: cross_video_repetition (8 pts)
    if metrics.cross_video_repetition <= 0.10:
        pts += 8
        notes.append(f"跨视频重复 {metrics.cross_video_repetition:.0%} 健康")
    elif metrics.cross_video_repetition <= 0.25:
        pts += 5
        notes.append(f"跨视频重复 {metrics.cross_video_repetition:.0%}（正常忠粉范围）")
    elif metrics.cross_video_repetition <= 0.40:
        pts += 2
        notes.append(f"跨视频重复 {metrics.cross_video_repetition:.0%} 偏高")
    else:
        notes.append(
            f"跨视频重复 {metrics.cross_video_repetition:.0%} —— 同一批人刷遍所有视频"
        )

    # Sub-component 3: C/L Ratio (5 pts)
    cl = metrics.cl_ratio * 100
    if cl >= 5:
        pts += 5
        notes.append(f"C/L {cl:.1f}% 健康（评论引发讨论）")
    elif cl >= 2:
        pts += 3
        notes.append(f"C/L {cl:.1f}% 正常")
    elif cl >= 1:
        pts += 1
    else:
        notes.append(f"C/L {cl:.2f}% < 1% —— 买赞警报")

    return (int(pts), "；".join(notes))


def _score_stability(stab: float) -> tuple[int, str]:
    w = WEIGHTS["stability"]
    if stab <= 0:
        return (0, "曝光数据缺失，无法评估稳定性")
    if stab < 3:
        return (w, f"波动 {stab:.1f}x 稳定")
    if stab < 5:
        return (int(w * 0.70), f"波动 {stab:.1f}x 可接受")
    if stab < 10:
        return (int(w * 0.30), f"波动 {stab:.1f}x 偏大")
    return (0, f"波动 {stab:.1f}x —— 数据不稳定")


def score_and_verdict(
    *,
    metrics: Metrics,
    price: float,
    avg_views: float,
    sample_size: int,
    vertical: str,
    currency: str = "USD",
) -> Verdict:
    bands = get_bands(vertical)

    # Hard red flags
    red_flags: list[str] = []
    if sample_size < 3:
        red_flags.append(f"样本仅 {sample_size} 条（< 3）")
    if metrics.cl_ratio < 0.01 and metrics.er < 0.001 and metrics.cl_ratio > 0:
        red_flags.append("C/L < 1% 且 ER < 0.1%（典型买赞模式）")
    if 0 < metrics.author_uniqueness < 0.40:
        red_flags.append(
            f"评论人独立度 {metrics.author_uniqueness:.0%} < 40%（重度水军嫌疑）"
        )
    if metrics.cross_video_repetition > 0.50:
        red_flags.append(
            f"跨视频重复率 {metrics.cross_video_repetition:.0%}（同一批账号刷遍所有视频）"
        )
    if metrics.stability > 10:
        red_flags.append(f"曝光波动 {metrics.stability:.1f}x（数据不稳定）")

    # Component scores
    cpm_pts, cpm_note = _score_cpm(metrics.cpm, vertical)
    er_pts, er_note = _score_er(metrics.er)
    ver_pts, ver_note = _score_view_er(metrics.view_er)
    auth_pts, auth_note = _score_authenticity(metrics)
    stab_pts, stab_note = _score_stability(metrics.stability)

    score = cpm_pts + er_pts + ver_pts + auth_pts + stab_pts

    breakdown = {
        "CPM 性价比": f"{cpm_pts}/{WEIGHTS['cpm']}",
        "ER 粉丝互动": f"{er_pts}/{WEIGHTS['er']}",
        "View ER 互动质量": f"{ver_pts}/{WEIGHTS['view_er']}",
        "评论真实性": f"{auth_pts}/{WEIGHTS['authenticity']}",
        "数据稳定性": f"{stab_pts}/{WEIGHTS['stability']}",
    }

    explanation = [cpm_note, er_note, ver_note, auth_note, stab_note]

    # Decision
    if red_flags:
        decision = "不合作"
    elif score >= 75:
        decision = "推进合作"
    elif score >= 60 and metrics.cpm > 0 and metrics.cpm <= bands.acceptable:
        decision = "推进合作"
    elif score >= 60 and metrics.cpm > bands.acceptable and metrics.cpm <= bands.expensive:
        decision = "砍价合作"
    elif score >= 45:
        decision = "小单试水"
    elif score >= 30:
        decision = "暂缓"
    else:
        decision = "不合作"

    target_price: float | None = None
    target_cpm: float | None = None
    pitch = ""
    if decision == "砍价合作" and metrics.cpm > 0 and avg_views > 0:
        # Drop CPM down to the upper edge of the acceptable band.
        target_cpm = bands.acceptable
        target_price = round(target_cpm * (avg_views / 1000.0), 2)
        pitch = (
            f"我们看了你近期视频的平均曝光约 {int(avg_views):,} 次，"
            f"按行业 CPM 上限 {currency} {target_cpm:.0f} 算合理报价是 "
            f"{currency} {target_price:,.2f}，能否到这个数？"
        )

    return Verdict(
        decision=decision,
        score=score,
        score_breakdown=breakdown,
        red_flags=red_flags,
        target_price=target_price,
        target_cpm=target_cpm,
        negotiation_pitch=pitch,
        explanation=explanation,
    )
