"""Parse various YouTube channel-input forms into a `ChannelLookup` record.

Accepted inputs:
    @MrBeast                                        → handle
    https://www.youtube.com/@MrBeast                → handle
    https://youtube.com/@MrBeast                    → handle
    UC...                                           → channel ID
    https://www.youtube.com/channel/UCx6OZ...       → channel ID
    https://www.youtube.com/c/somecustom            → custom URL (best-effort: use as handle)
    https://www.youtube.com/user/legacyName         → legacy username
    https://youtu.be/<vid>                          → video URL (we resolve to its channel)
    https://www.youtube.com/watch?v=<vid>           → video URL (we resolve to its channel)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass
class ChannelLookup:
    """How the user identified a channel. Only one of these is non-empty."""

    handle: str = ""  # WITH leading "@", e.g. "@MrBeast"
    channel_id: str = ""  # "UC..." 24 chars
    legacy_username: str = ""  # /user/<x>
    video_id: str = ""  # if the user gave a video URL, resolve channel server-side


_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
_HANDLE_BODY_RE = re.compile(r"^[A-Za-z0-9._-]{3,30}$")


def parse_channel_input(input_str: str) -> ChannelLookup:
    """Parse user input into a ChannelLookup. Raises ValueError on malformed input."""
    if not input_str or not input_str.strip():
        raise ValueError("Empty input. Pass a handle (@MrBeast), a channel URL, or a video URL.")

    s = input_str.strip()

    # Bare channel ID (UC..., 24 chars)
    if _CHANNEL_ID_RE.match(s):
        return ChannelLookup(channel_id=s)

    # Bare handle, with or without "@"
    if "/" not in s and "." not in s:
        body = s.lstrip("@")
        if _HANDLE_BODY_RE.match(body):
            return ChannelLookup(handle=f"@{body}")
        raise ValueError(f"Could not parse {input_str!r} as a YouTube handle.")

    # URL — make sure it has scheme
    if "://" not in s:
        s = "https://" + s
    parsed = urlparse(s)
    host = (parsed.netloc or "").lower().lstrip("www.")
    if host not in {"youtube.com", "m.youtube.com", "youtu.be", "youtubekids.com"}:
        raise ValueError(
            f"Not a YouTube URL: {input_str!r}. "
            "Expected youtube.com / youtu.be, or a bare handle like @MrBeast."
        )

    # youtu.be/<videoId>
    if host == "youtu.be":
        vid = parsed.path.strip("/").split("/")[0] if parsed.path else ""
        if vid:
            return ChannelLookup(video_id=vid)
        raise ValueError(f"No video id in {input_str!r}.")

    parts = [p for p in parsed.path.split("/") if p]

    # /watch?v=<id>
    if parts and parts[0] == "watch":
        q = parse_qs(parsed.query or "")
        vids = q.get("v") or []
        if vids:
            return ChannelLookup(video_id=vids[0])
        raise ValueError(f"watch URL has no v= param: {input_str!r}.")

    # /channel/UCxxxx
    if len(parts) >= 2 and parts[0] == "channel":
        if _CHANNEL_ID_RE.match(parts[1]):
            return ChannelLookup(channel_id=parts[1])
        raise ValueError(f"Malformed channel ID in {input_str!r}: {parts[1]!r}")

    # /user/<legacy>
    if len(parts) >= 2 and parts[0] == "user":
        return ChannelLookup(legacy_username=parts[1])

    # /@handle  or /c/customname
    if parts:
        first = parts[0]
        if first.startswith("@"):
            body = first.lstrip("@")
            if _HANDLE_BODY_RE.match(body):
                return ChannelLookup(handle=f"@{body}")
        if first == "c" and len(parts) >= 2:
            # Treat /c/<name> as a handle attempt — YouTube has merged most of these.
            return ChannelLookup(handle=f"@{parts[1]}")

    raise ValueError(f"Could not extract a channel identifier from {input_str!r}.")


def channel_url(channel_id: str = "", handle: str = "") -> str:
    """Public-facing channel URL for the report."""
    if channel_id:
        return f"https://www.youtube.com/channel/{channel_id}"
    if handle:
        h = handle if handle.startswith("@") else f"@{handle}"
        return f"https://www.youtube.com/{h}"
    return ""
