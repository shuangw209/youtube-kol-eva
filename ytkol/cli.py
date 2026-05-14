"""Command-line interface."""

from __future__ import annotations

import os
import sys

import click
from rich.console import Console

from ytkol.calculator import calculate_metrics
from ytkol.client import ChannelNotFound, YouTubeAPIError, YouTubeClient
from ytkol.config import VERTICALS
from ytkol.models import Report
from ytkol.report import render_table, to_json, write_json_file
from ytkol.url_utils import channel_url, parse_channel_input
from ytkol.verdict import score_and_verdict


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except ImportError:
        click.echo(
            "[warn] python-dotenv missing; .env will not be auto-loaded.", err=True
        )


@click.group()
@click.version_option(package_name="youtube-kol-eva")
def main() -> None:
    """YouTube KOL evaluator — 6 core metrics + comment authenticity + verdict."""
    _load_env()


@main.command()
@click.argument("channel_input")
@click.option("--price", "-p", type=float, required=True, help="Quoted price for one sponsored video.")
@click.option(
    "--recent-n",
    "-n",
    type=int,
    default=None,
    help="How many most-recent uploads to sample (default 10, env DEFAULT_RECENT_N).",
)
@click.option(
    "--comments-per-video",
    type=int,
    default=None,
    help="How many top-level comments per video to scan for authenticity "
    "(default 100, env DEFAULT_COMMENTS_PER_VIDEO).",
)
@click.option(
    "--vertical",
    type=click.Choice(sorted(VERTICALS.keys())),
    default=None,
    help="Industry vertical for CPM benchmarking (default tech_ai, env DEFAULT_VERTICAL).",
)
@click.option("--currency", "-c", default=None, help="Currency label for the price.")
@click.option("--api-key", default=None, help="YouTube API key (default env YOUTUBE_API_KEY).")
@click.option(
    "--include-shorts",
    is_flag=True,
    default=False,
    help="Include videos that look like Shorts (≤ 60 s). Off by default.",
)
@click.option(
    "--json",
    "json_path",
    type=click.Path(),
    default=None,
    help="If set, also write the full JSON report to this path.",
)
@click.option(
    "--no-table",
    is_flag=True,
    help="Suppress the terminal table; print JSON to stdout instead.",
)
def evaluate(
    channel_input: str,
    price: float,
    recent_n: int | None,
    comments_per_video: int | None,
    vertical: str | None,
    currency: str | None,
    api_key: str | None,
    include_shorts: bool,
    json_path: str | None,
    no_table: bool,
) -> None:
    """Evaluate a YouTube channel.

    CHANNEL_INPUT can be:

    \b
      @MrBeast                                    (handle)
      https://www.youtube.com/@MrBeast            (handle URL)
      UCx6OZ-1Hdg9OXhJzrqNkSZA                    (channel ID)
      https://www.youtube.com/channel/UCx6OZ...   (channel URL)
      https://www.youtube.com/watch?v=...         (video URL → resolved)
    """
    console = Console()

    api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        console.print(
            "[red]No YOUTUBE_API_KEY set.[/red] Add it to .env or pass --api-key. "
            "See README for how to create one."
        )
        sys.exit(2)

    try:
        lookup = parse_channel_input(channel_input)
    except ValueError as e:
        console.print(f"[red]Bad input:[/red] {e}")
        sys.exit(2)

    recent_n = recent_n or int(os.environ.get("DEFAULT_RECENT_N", "10"))
    comments_per_video = comments_per_video or int(
        os.environ.get("DEFAULT_COMMENTS_PER_VIDEO", "100")
    )
    vertical = vertical or os.environ.get("DEFAULT_VERTICAL", "tech_ai")
    currency = currency or os.environ.get("DEFAULT_CURRENCY", "USD")

    console.print(
        f"[cyan]Resolving channel[/cyan] from [bold]{channel_input}[/bold]…"
    )

    notes: list[str] = []

    try:
        with YouTubeClient(api_key) as yt:
            stats = yt.resolve_channel(lookup)
            console.print(
                f"[green]✓[/green] Found channel [bold]{stats.title}[/bold] "
                f"({stats.subscribers:,} subscribers)"
            )

            console.print(
                f"[cyan]Pulling[/cyan] {recent_n} most-recent uploads…"
            )
            video_ids = yt.recent_uploads(stats.uploads_playlist_id, limit=recent_n * 2)
            samples = yt.fetch_video_stats(video_ids)

            if not include_shorts:
                before = len(samples)
                samples = [s for s in samples if not s.is_short]
                if before != len(samples):
                    notes.append(
                        f"Skipped {before - len(samples)} likely Shorts (≤ 60 s). "
                        "Pass --include-shorts to include them."
                    )

            samples = samples[:recent_n]

            console.print(
                f"[cyan]Pulling[/cyan] up to {comments_per_video} comments per video "
                f"for {len(samples)} videos…"
            )
            for s in samples:
                # Skip videos with comments=0 (or comments disabled — same end result)
                if s.comments == 0:
                    continue
                s.commenter_ids = yt.fetch_top_level_commenters(
                    s.video_id, limit=comments_per_video
                )
    except ChannelNotFound as e:
        console.print(f"[red]Channel not found:[/red] {e}")
        sys.exit(3)
    except YouTubeAPIError as e:
        console.print(f"[red]YouTube API error:[/red] {e}")
        sys.exit(4)

    metrics, calc_notes = calculate_metrics(
        subscribers=stats.subscribers,
        samples=samples,
        price=price,
    )
    notes.extend(calc_notes)

    avg_views = sum(s.views for s in samples) / len(samples) if samples else 0.0

    verdict = score_and_verdict(
        metrics=metrics,
        price=price,
        avg_views=avg_views,
        sample_size=len(samples),
        vertical=vertical,
        currency=currency,
    )

    total_comments = sum(len(s.commenter_ids) for s in samples)
    unique_commenters = len({c for s in samples for c in s.commenter_ids})

    report = Report(
        handle=stats.handle or lookup.handle,
        channel_id=stats.channel_id,
        channel_title=stats.title,
        channel_url=channel_url(channel_id=stats.channel_id, handle=stats.handle),
        subscribers=stats.subscribers,
        price=price,
        currency=currency,
        vertical=vertical,
        sample_size=len(samples),
        avg_views=avg_views,
        avg_likes=sum(s.likes for s in samples) / len(samples) if samples else 0.0,
        avg_comments=sum(s.comments for s in samples) / len(samples) if samples else 0.0,
        total_comments_collected=total_comments,
        unique_commenters=unique_commenters,
        metrics=metrics,
        verdict=verdict,
        samples=samples,
        notes=notes,
    )

    if no_table:
        click.echo(to_json(report))
    else:
        render_table(report, console=console)

    if json_path:
        write_json_file(report, json_path)
        console.print(f"[green]Wrote[/green] JSON report to [bold]{json_path}[/bold]")


@main.command()
def doctor() -> None:
    """Verify that YOUTUBE_API_KEY works and the API is reachable."""
    console = Console()
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        console.print("[red]✗[/red] YOUTUBE_API_KEY is not set. Add it to .env.")
        sys.exit(1)
    try:
        with YouTubeClient(api_key) as yt:
            # 1-unit videos.list call against a known-public video.
            r = yt._get(
                "videos",
                {"part": "id,snippet", "id": "dQw4w9WgXcQ", "maxResults": 1},
            )
            items = r.get("items") or []
            if not items:
                console.print(
                    "[yellow]![/yellow] API responded but returned no items. "
                    "Quota may be exhausted, or the test video is unavailable."
                )
                sys.exit(1)
        console.print("[green]✓[/green] YouTube API key works.")
    except YouTubeAPIError as e:
        console.print(f"[red]✗[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
