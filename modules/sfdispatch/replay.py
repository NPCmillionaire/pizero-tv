"""Spread a batch of calls over a time window so pins drop steadily, in order."""
import bisect

SPREAD = 0.9  # use 90% of the window so the last call lands before the next poll


def schedule(batch, start, window):
    b = sorted(batch, key=lambda c: c.received)
    if not b:
        return []
    first = b[0].received
    span = (b[-1].received - first).total_seconds()
    if span <= 0:
        return [(start, c) for c in b]
    return [(start + (c.received - first).total_seconds() / span * SPREAD * window, c) for c in b]


class Replayer:
    def __init__(self, window=60.0):
        self.window = window
        self._q = []  # sorted list of (time, seq, call)
        self._seq = 0

    def add(self, batch, now, initial=False):
        items = [(now, c) for c in sorted(batch, key=lambda c: c.received)] if initial \
            else schedule(batch, now, self.window)
        for t, c in items:
            bisect.insort(self._q, (t, self._seq, c))
            self._seq += 1

    def due(self, now):
        i = bisect.bisect_right(self._q, (now, float("inf")))
        out, self._q = [c for _, _, c in self._q[:i]], self._q[i:]
        return out
