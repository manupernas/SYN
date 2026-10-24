"""SYN: reconnect policy for an existing libmpv source.

Pure Python (no GTK, FFmpeg, credentials, network access or DVR modification).
Call sample() from the main loop with a snapshot taken by libmpv's control
thread. All times use time.monotonic().
"""
from __future__ import annotations
from dataclasses import dataclass
import math

VISUAL_BUFFER_SECONDS = 2.6
RETRY_BUFFER_SECONDS = 8.0
VISUAL_STALL_SECONDS = 7.0
RETRY_STALL_SECONDS = 12.0
INITIAL_LOAD_GRACE_SECONDS = 15.0


@dataclass(frozen=True)
class ReconnectDecision:
    visible: bool = False
    retry: bool = False
    attempt: int = 0
    reason: str = ''


class RecoveryWatch:
    def __init__(self):
        self.clear()

    def clear(self):
        self.url = None
        self.first_seen = 0.0
        self.position = None
        self.last_progress = None
        self.last_position_change = None
        self.buffer_start = None
        self.error_since = None
        self.retries = 0
        self.next_retry = 0.0
        self.last_reconnect = 0.0
        self.started_playing = False

    def error(self, when):
        if self.url:
            self.error_since = float(when)

    def sample(self, now, url, position=None, *, paused=False, buffering=False,
               loading=False, seeking=False, enabled=True):
        now = float(now)
        if not enabled or not url or paused or seeking:
            if not enabled or not url:
                self.clear()
            else:
                # Deliberate pause/seek is not a connection failure.
                self.first_seen = now
                self.last_progress = now
                self.last_position_change = now
                self.buffer_start = None
                self.error_since = None
                self.retries = 0
            return ReconnectDecision()
        if url != self.url:
            self.clear()
            self.url = url
            self.first_seen = now
            self.last_progress = now
            self.last_position_change = now

        valid_pos = isinstance(position, (int, float)) and math.isfinite(position)
        if valid_pos:
            position = float(position)
            if self.position is None:
                self.position = position
                self.last_position_change = now
            elif position < self.position - 1.25:
                # MPEG-TS/HLS clock discontinuity. Await actual forward
                # progress on the new timeline before declaring recovery.
                self.position = position
                self.last_position_change = now
            elif position > self.position + 0.30:
                self.position = position
                self.last_position_change = now
                self.last_progress = now
                self.started_playing = True
                self.buffer_start = None
                self.error_since = None
                self.retries = 0
                self.next_retry = 0
                return ReconnectDecision()

        if buffering:
            if self.buffer_start is None:
                self.buffer_start = now
        else:
            self.buffer_start = None

        buffered = now - self.buffer_start if self.buffer_start is not None else 0.0
        stalled = now - (self.last_position_change if self.last_position_change is not None else now)
        initial = now - self.first_seen
        error = self.error_since is not None

        # A short resolution change or normal HLS playlist rebuffering must
        # not restart the whole decoder. Don't rely on GL redraw timestamps:
        # GL can keep rendering the same stalled frame indefinitely.
        reason = ''
        if error:
            reason = 'error'
        elif buffered >= VISUAL_BUFFER_SECONDS:
            reason = 'buffer'
        elif self.started_playing and not loading and stalled >= VISUAL_STALL_SECONDS:
            reason = 'stall'
        elif loading and initial >= INITIAL_LOAD_GRACE_SECONDS:
            reason = 'initial-load'

        if not reason:
            return ReconnectDecision()

        retry_due = (error or buffered >= RETRY_BUFFER_SECONDS or
                     (self.started_playing and stalled >= RETRY_STALL_SECONDS) or
                     (loading and initial >= INITIAL_LOAD_GRACE_SECONDS))
        if retry_due and now >= self.next_retry:
            self.retries += 1
            # Back off repeated failures; never hammer the IPTV provider.
            self.next_retry = now + min(30.0, 2.0 ** min(self.retries, 5) * 2.0)
            self.last_reconnect = now
            self.error_since = None
            self.buffer_start = now if buffering else None
            self.last_position_change = now
            self.first_seen = now
            return ReconnectDecision(True, True, self.retries, reason)
        return ReconnectDecision(True, False, self.retries, reason)
