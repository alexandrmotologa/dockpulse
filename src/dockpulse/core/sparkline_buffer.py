"""Rolling window time-series buffer and Unicode sparkline renderer."""

from collections import deque

SPARK_CHARS = (" ", "▂", "▃", "▄", "▅", "▆", "▇", "█")


class SparklineBuffer:
    """Ring buffer maintaining rolling numerical samples and generating Unicode sparklines."""

    def __init__(self, capacity: int = 60) -> None:
        self.capacity = max(2, capacity)
        self._buffer: deque[float] = deque(maxlen=self.capacity)

    def push(self, value: float) -> None:
        """Add a numerical sample to the buffer."""
        self._buffer.append(float(value))

    def clear(self) -> None:
        """Reset the buffer."""
        self._buffer.clear()

    @property
    def values(self) -> list[float]:
        return list(self._buffer)

    @property
    def latest(self) -> float:
        return self._buffer[-1] if self._buffer else 0.0

    @property
    def min_val(self) -> float:
        return min(self._buffer) if self._buffer else 0.0

    @property
    def max_val(self) -> float:
        return max(self._buffer) if self._buffer else 0.0

    @property
    def avg_val(self) -> float:
        return sum(self._buffer) / len(self._buffer) if self._buffer else 0.0

    def render(self, width: int = 30, max_scale: float | None = None) -> str:
        """Render samples as a Unicode sparkline string.

        Args:
            width: Number of sparkline characters to render.
            max_scale: Optional fixed ceiling (e.g. 100.0 for percentages). If None, scales to max_val.
        """
        if not self._buffer:
            return " " * width

        # Take the most recent `width` samples
        samples = list(self._buffer)[-width:]
        if len(samples) < width:
            # Pad on the left with empty spaces
            pad = [" "] * (width - len(samples))
        else:
            pad = []

        low = 0.0
        high = max_scale if max_scale is not None else max(self.max_val, 0.001)

        val_range = max(0.0001, high - low)
        num_levels = len(SPARK_CHARS)

        chars = []
        for val in samples:
            clamped = max(low, min(high, val))
            normalized = (clamped - low) / val_range
            idx = int(normalized * (num_levels - 1))
            idx = max(0, min(num_levels - 1, idx))
            chars.append(SPARK_CHARS[idx])

        return "".join(pad) + "".join(chars)
