"""Pretty terminal output + JSON serialization."""

from __future__ import annotations

import json

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ytkol.models import Report


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _fmt_num(x: float) -> str:
    if x >= 1_000_000:
        return f"{x / 1_000_000:.2f}M"
    if x >= 1_000:
        return f"{x / 1_000:.2f}K"
    return f"{x:.0f}"


def _fmt_money(x: float, currency: str) -> str:
    return f"{currency} {x:,.2f}"


_DECISION_COLOR = {
    "推进合作": "bold green",
    "砍价合作": "bold yellow",
    "小单试水": "bold cyan",
    "暂缓": "bold yellow",
    "不合作": "bold red",
}


def render_table(report: Report, console: Console | None = None) -> None:
    console = console or Console()

    head = Table.grid(padding=(0, 2))
    head.add_column(justify="right", style="bold")
    head.add_column()
    head.add_row("Channel", f"{report.channel_title}  ({report.channel_url})")
    head.add_row("Subscribers", _fmt_num(report.subscribers))
    head.add_row("Vertical", report.vertical)
    head.add_row("Quoted price", _fmt_money(report.price, report.currency))
    head.add_row("Sample size", f"{report.sample_size} recent uploads")
    head.add_row(
        "Avg per video",
        f"views {_fmt_num(report.avg_views)} | likes {_fmt_num(report.avg_likes)} | "
        f"comments {_fmt_num(report.avg_comments)}",
    )
    head.add_row(
        "Comments collected",
        f"{report.total_comments_collected} (unique authors: {report.unique_commenters})",
    )
    console.print(Panel(head, title="KOL Snapshot", border_style="cyan"))

    metrics = report.metrics
    t = Table(title="The 6 Core Metrics", header_style="bold magenta")
    t.add_column("Metric", style="bold")
    t.add_column("Value", justify="right")
    t.add_column("Formula", style="dim")
    t.add_row("ER (粉丝互动率)", _fmt_pct(metrics.er), "(likes+comments) / subscribers")
    t.add_row("View ER (曝光互动率)", _fmt_pct(metrics.view_er), "(likes+comments) / avg_views")
    t.add_row("C/L Ratio (评论深度比)", _fmt_pct(metrics.cl_ratio), "comments / likes")
    t.add_row("Reach Rate (粉丝触达率)", _fmt_pct(metrics.reach_rate), "avg_views / subscribers")
    t.add_row("Stability (数据稳定性)", f"{metrics.stability:.2f}x", "max_views / min_views")
    t.add_row("CPM (千次曝光成本)", _fmt_money(metrics.cpm, report.currency), "price / (avg_views/1000)")
    console.print(t)

    a = Table(title="Comment Authenticity", header_style="bold magenta")
    a.add_column("Metric", style="bold")
    a.add_column("Value", justify="right")
    a.add_column("Reading", style="dim")
    a.add_row(
        "Author uniqueness",
        _fmt_pct(metrics.author_uniqueness),
        "unique authors / total comments — 越高越真实",
    )
    a.add_row(
        "Cross-video repetition",
        _fmt_pct(metrics.cross_video_repetition),
        "≥2 videos 重复评论占比 — 越低越真实",
    )
    console.print(a)

    v = report.verdict
    color = _DECISION_COLOR.get(v.decision, "bold")
    verdict_panel = Table.grid(padding=(0, 2))
    verdict_panel.add_column(justify="right", style="bold")
    verdict_panel.add_column()
    verdict_panel.add_row("Decision", f"[{color}]{v.decision}[/{color}]")
    verdict_panel.add_row("Score", f"{v.score} / 100")
    for dim, val in v.score_breakdown.items():
        verdict_panel.add_row(f"  {dim}", val)
    if v.red_flags:
        verdict_panel.add_row("Red flags", "\n".join(f"⚠ {x}" for x in v.red_flags))
    if v.target_price is not None:
        verdict_panel.add_row(
            "目标价",
            f"{_fmt_money(v.target_price, report.currency)} (CPM {v.target_cpm:.0f})",
        )
        verdict_panel.add_row("谈判说辞", v.negotiation_pitch)
    if v.explanation:
        verdict_panel.add_row("说明", "\n".join(f"• {e}" for e in v.explanation))
    console.print(Panel(verdict_panel, title="Verdict", border_style=color.split()[-1]))

    if report.notes:
        console.print(
            Panel(
                "\n".join(f"• {n}" for n in report.notes),
                title="Notes",
                border_style="yellow",
                title_align="left",
            )
        )

    if report.samples:
        s = Table(title=f"Samples ({len(report.samples)})")
        s.add_column("#", justify="right", style="dim")
        s.add_column("Published")
        s.add_column("Title", overflow="fold")
        s.add_column("Views", justify="right")
        s.add_column("Likes", justify="right")
        s.add_column("Comments", justify="right")
        for i, sample in enumerate(report.samples, 1):
            tag = " [dim](Short)[/dim]" if sample.is_short else ""
            s.add_row(
                str(i),
                sample.published_at[:10] if sample.published_at else "—",
                f"{sample.title[:60]}{tag}",
                _fmt_num(sample.views),
                _fmt_num(sample.likes),
                _fmt_num(sample.comments),
            )
        console.print(s)


def to_json(report: Report, *, pretty: bool = True) -> str:
    return json.dumps(
        report.to_dict(),
        indent=2 if pretty else None,
        ensure_ascii=False,
    )


def write_json_file(report: Report, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_json(report))
