"""Thin YouTube Data API v3 client.

Only the four endpoints we need:
    * channels.list      — channel stats + uploads playlist id
    * playlistItems.list — list of recent uploads
    * videos.list        — per-video stats (views/likes/comments) + duration
    * commentThreads.list — top-level comments (we want author IDs)

Quota cost (each is 1 unit):
    channels.list, playlistItems.list, videos.list, commentThreads.list

For one channel × 10 videos × 100 comments:
    1 + 1 + 1 + 10 = 13 units (plenty under the 10 000/day free quota).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterator

import httpx

from ytkol.models import Sample
from ytkol.url_utils import ChannelLookup

log = logging.getLogger(__name__)

API_ROOT = "https://www.googleapis.com/youtube/v3"


class YouTubeAPIError(RuntimeError):
    """Raised on a non-2xx YouTube API response, or quota issues."""


class ChannelNotFound(YouTubeAPIError):
    pass


@dataclass
class ChannelStats:
    channel_id: str
    title: str
    handle: str = ""
    subscribers: int = 0
    total_views: int = 0
    total_videos: int = 0
    uploads_playlist_id: str = ""
    description: str = ""


# ISO-8601 duration parser for YouTube's PT#H#M#S format
_DURATION_RE = re.compile(
    r"^PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?$"
)


def parse_iso_duration(text: str) -> int:
    """Return total seconds for a YouTube ISO-8601 duration, or 0 if unparseable."""
    if not text:
        return 0
    m = _DURATION_RE.match(text)
    if not m:
        return 0
    h = int(m.group("h") or 0)
    mm = int(m.group("m") or 0)
    s = int(m.group("s") or 0)
    return h * 3600 + mm * 60 + s


class YouTubeClient:
    """Tiny synchronous client wrapper. Uses httpx so retries/timeouts are sane."""

    def __init__(self, api_key: str, *, timeout: float = 15.0) -> None:
        if not api_key:
            raise ValueError("YOUTUBE_API_KEY is required")
        self._key = api_key
        self._client = httpx.Client(timeout=timeout)

    # -------- low-level --------

    def _get(self, path: str, params: dict) -> dict:
        params = {**params, "key": self._key}
        r = self._client.get(f"{API_ROOT}/{path}", params=params)
        if r.status_code == 200:
            return r.json()
        try:
            err = r.json().get("error", {})
            msg = err.get("message", r.text)
        except Exception:
            msg = r.text
        if r.status_code in (401, 403) and "quota" in msg.lower():
            raise YouTubeAPIError(f"YouTube API quota exceeded: {msg}")
        if r.status_code == 400 and "API key not valid" in msg:
            raise YouTubeAPIError(
                "API key rejected by YouTube. Check it's correct and that "
                "YouTube Data API v3 is ENABLED for the project that owns it."
            )
        raise YouTubeAPIError(f"YouTube API {r.status_code}: {msg}")

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "YouTubeClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -------- high-level --------

    def resolve_channel(self, lookup: ChannelLookup) -> ChannelStats:
        """Resolve any of {handle, channel_id, legacy_username, video_id} → channel."""
        params: dict = {
            "part": "snippet,statistics,contentDetails",
            "maxResults": 1,
        }
        if lookup.channel_id:
            params["id"] = lookup.channel_id
        elif lookup.handle:
            params["forHandle"] = lookup.handle  # forHandle wants e.g. "@MrBeast"
        elif lookup.legacy_username:
            params["forUsername"] = lookup.legacy_username
        elif lookup.video_id:
            # Resolve via videos.list → snippet.channelId
            vd = self._get(
                "videos",
                {"part": "snippet", "id": lookup.video_id, "maxResults": 1},
            )
            items = vd.get("items") or []
            if not items:
                raise ChannelNotFound(f"Video {lookup.video_id} not found.")
            ch_id = items[0]["snippet"]["channelId"]
            params["id"] = ch_id
        else:
            raise ChannelNotFound("Empty lookup record.")

        data = self._get("channels", params)
        items = data.get("items") or []
        if not items:
            raise ChannelNotFound(
                f"No channel matched lookup={lookup}. Double-check the handle/ID, "
                "or ensure the channel isn't terminated."
            )
        item = items[0]
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        details = item.get("contentDetails", {}).get("relatedPlaylists", {})
        return ChannelStats(
            channel_id=item["id"],
            title=snippet.get("title", ""),
            handle=snippet.get("customUrl", "") or "",
            subscribers=int(stats.get("subscriberCount") or 0),
            total_views=int(stats.get("viewCount") or 0),
            total_videos=int(stats.get("videoCount") or 0),
            uploads_playlist_id=details.get("uploads", "") or "",
            description=snippet.get("description", "") or "",
        )

    def recent_uploads(
        self,
        uploads_playlist_id: str,
        *,
        limit: int = 10,
    ) -> list[str]:
        """Return up to `limit` most-recent video IDs from the channel uploads playlist."""
        if not uploads_playlist_id:
            return []
        ids: list[str] = []
        page_token: str | None = None
        while len(ids) < limit:
            params = {
                "part": "contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(50, limit - len(ids)),
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get("playlistItems", params)
            for item in data.get("items", []):
                vid = item.get("contentDetails", {}).get("videoId")
                if vid:
                    ids.append(vid)
                    if len(ids) >= limit:
                        break
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return ids

    def fetch_video_stats(self, video_ids: list[str]) -> list[Sample]:
        """Batch-fetch stats for video IDs (up to 50 per call, 1 unit each)."""
        if not video_ids:
            return []
        out: list[Sample] = []
        # videos.list accepts up to 50 ids at once, comma-separated
        for i in range(0, len(video_ids), 50):
            chunk = video_ids[i : i + 50]
            data = self._get(
                "videos",
                {
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(chunk),
                    "maxResults": 50,
                },
            )
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                details = item.get("contentDetails", {})
                duration = parse_iso_duration(details.get("duration", ""))
                # Heuristic: <= 60s is almost certainly a Short. (YouTube doesn't
                # reliably tag shorts in the API.)
                is_short = 0 < duration <= 60
                vid = item["id"]
                # Some channels disable likes/comments — those fields are absent.
                likes = int(stats.get("likeCount") or 0)
                comments = int(stats.get("commentCount") or 0)
                views = int(stats.get("viewCount") or 0)
                out.append(
                    Sample(
                        video_id=vid,
                        url=f"https://www.youtube.com/watch?v={vid}",
                        title=snippet.get("title", ""),
                        published_at=snippet.get("publishedAt", ""),
                        duration_seconds=duration,
                        is_short=is_short,
                        views=views,
                        likes=likes,
                        comments=comments,
                    )
                )
        return out

    def fetch_top_level_commenters(
        self, video_id: str, *, limit: int = 100
    ) -> list[str]:
        """Return up to `limit` distinct top-level commenter author IDs for a video.

        Comments may be disabled — in that case we get a 403 and return [].
        """
        if not video_id:
            return []
        ids: list[str] = []
        page_token: str | None = None
        try:
            while len(ids) < limit:
                params: dict = {
                    "part": "snippet",
                    "videoId": video_id,
                    "maxResults": min(100, limit - len(ids)),
                    "textFormat": "plainText",
                    "order": "time",
                }
                if page_token:
                    params["pageToken"] = page_token
                data = self._get("commentThreads", params)
                for item in data.get("items", []):
                    s = (
                        item.get("snippet", {})
                        .get("topLevelComment", {})
                        .get("snippet", {})
                    )
                    author = s.get("authorChannelId", {}).get("value", "")
                    if author:
                        ids.append(author)
                        if len(ids) >= limit:
                            break
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        except YouTubeAPIError as e:
            # Comments disabled on this video, or some other transient issue —
            # return what we have so far. The caller treats this as "no signal".
            log.debug("commentThreads fetch failed for %s: %s", video_id, e)
        return ids
