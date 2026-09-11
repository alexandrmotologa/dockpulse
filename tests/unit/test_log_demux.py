"""Tests for LogMultiplexer and Docker framing header parsing."""

import struct

from dockpulse.core.log_multiplexer import LogMultiplexer


def test_log_multiplexer_add_and_filter() -> None:
    mux = LogMultiplexer(max_lines=10)
    mux.add_line(1, "GET /health 200 OK")
    mux.add_line(2, "FATAL: connection refused to redis")
    mux.add_line(1, "POST /orders 201 Created")

    assert mux.count == 3

    # All lines
    all_lines = mux.get_lines()
    assert len(all_lines) == 3

    # Filter for redis error
    filtered = mux.get_lines("redis")
    assert len(filtered) == 1
    assert filtered[0].is_stderr is True
    assert "ERR" in filtered[0].render_markup()

    # Regex search
    regex_filtered = mux.get_lines(r"\b(GET|POST)\b")
    assert len(regex_filtered) == 2


def test_parse_docker_frames() -> None:
    # Build 2 frames: one stdout and one stderr
    text1 = b"Hello from stdout\n"
    frame1 = struct.pack(">BxxxI", 1, len(text1)) + text1

    text2 = b"Error from stderr\n"
    frame2 = struct.pack(">BxxxI", 2, len(text2)) + text2

    raw_stream = bytearray(frame1 + frame2)
    parsed = LogMultiplexer.parse_docker_frames(raw_stream)

    assert len(parsed) == 2
    assert parsed[0] == (1, "Hello from stdout")
    assert parsed[1] == (2, "Error from stderr")
    assert len(raw_stream) == 0  # Buffer fully consumed


def test_parse_partial_docker_frames() -> None:
    # Test incomplete buffer does not crash and leaves partial bytes intact
    text = b"Partial payload"
    header = struct.pack(">BxxxI", 1, len(text))

    # Feed header + only half of payload
    partial_buffer = bytearray(header + text[:5])
    parsed = LogMultiplexer.parse_docker_frames(partial_buffer)

    assert len(parsed) == 0
    assert len(partial_buffer) == 8 + 5  # Left in buffer for next chunk
