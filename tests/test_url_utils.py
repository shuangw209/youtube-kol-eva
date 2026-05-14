"""Tests for channel-input parsing."""

import pytest

from ytkol.url_utils import parse_channel_input


def test_handle_with_at():
    r = parse_channel_input("@MrBeast")
    assert r.handle == "@MrBeast"


def test_handle_without_at():
    r = parse_channel_input("MrBeast")
    assert r.handle == "@MrBeast"


def test_handle_url():
    r = parse_channel_input("https://www.youtube.com/@MrBeast")
    assert r.handle == "@MrBeast"


def test_channel_id_bare():
    r = parse_channel_input("UCx6OZ-1Hdg9OXhJzrqNkSZA")
    assert r.channel_id == "UCx6OZ-1Hdg9OXhJzrqNkSZA"


def test_channel_id_url():
    r = parse_channel_input("https://www.youtube.com/channel/UCx6OZ-1Hdg9OXhJzrqNkSZA")
    assert r.channel_id == "UCx6OZ-1Hdg9OXhJzrqNkSZA"


def test_legacy_user_url():
    r = parse_channel_input("https://www.youtube.com/user/PewDiePie")
    assert r.legacy_username == "PewDiePie"


def test_video_url():
    r = parse_channel_input("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert r.video_id == "dQw4w9WgXcQ"


def test_youtu_be_short_url():
    r = parse_channel_input("https://youtu.be/dQw4w9WgXcQ")
    assert r.video_id == "dQw4w9WgXcQ"


def test_c_prefix_url():
    r = parse_channel_input("https://www.youtube.com/c/somecreator")
    assert r.handle == "@somecreator"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "https://example.com/foo",  # not youtube
        "https://www.youtube.com/channel/notavalidid",  # malformed channel id
    ],
)
def test_invalid(bad):
    with pytest.raises(ValueError):
        parse_channel_input(bad)
