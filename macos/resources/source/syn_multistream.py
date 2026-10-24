"""SYN two simultaneous DVR streams: admission checks and source occupancy.

This is deliberately an independent, offline-testable policy module.  The
existing DVR worker is still responsible for launching and supervising FFmpeg.
"""
from __future__ import annotations
import math
import time

LIVE_STATES = frozenset(('scheduled', 'running'))
DEFAULT_CONNECTIONS = 1


def profile_limit(profile):
    try:
        number = int(profile.get('max_connections', DEFAULT_CONNECTIONS))
    except (ValueError, TypeError, AttributeError):
        number = DEFAULT_CONNECTIONS
    return min(4, max(1, number))


def same_profile(job, profile_id):
    # Old DVR entries have no profile ID: charge them conservatively against
    # whichever current profile is being used, rather than ignore live streams.
    return (not job.get('profile_id') or not profile_id
            or str(job.get('profile_id')) == str(profile_id))


def active_jobs(db, profile_id):
    return [j for j in db.get('jobs', []) if isinstance(j, dict)
            and same_profile(j, profile_id)
            and j.get('status') == 'running' and not j.get('stop_requested')]


def admitted_jobs(db, profile_id):
    return [j for j in db.get('jobs', []) if isinstance(j, dict)
            and same_profile(j, profile_id)
            and j.get('status') in LIVE_STATES and not j.get('stop_requested')]


def intervals_overlap(start_a, end_a, start_b, end_b):
    """Treat [start, end) as half-open; indefinite jobs have infinite end."""
    return max(float(start_a), float(start_b)) < min(
        float(end_a) if end_a is not None else math.inf,
        float(end_b) if end_b is not None else math.inf,
    )


def can_schedule(db, profile_id, start, end, slots):
    """Reject a proposed booking if it raises *peak* overlaps over slots.

    Only examine the candidate time interval; pre-existing unrelated conflicts
    should not block a free slot at a different time of day.
    """
    slots = min(4, max(1, int(slots)))
    a = float(start)
    b = float(end) if end is not None else math.inf
    if b <= a:
        return False
    events = [(a, 1), (b, -1)]
    for j in admitted_jobs(db, profile_id):
        lo = max(a, float(j.get('start', 0)))
        hi = min(b, float(j['end']) if j.get('end') is not None else math.inf)
        if lo < hi:
            events.extend(((lo, 1), (hi, -1)))
    concurrent = 0
    # End events must be processed BEFORE start events at equal timestamps.
    for _, change in sorted(events, key=lambda e: (e[0], e[1])):
        concurrent += change
        if concurrent > slots:
            return False
    return True


def can_start_now(db, job, active_count=None):
    slots = profile_limit({'max_connections': job.get('max_connections', 1)})
    running = active_jobs(db, job.get('profile_id'))
    if active_count is not None:
        return active_count < slots
    return len(running) < slots


def should_release_playback(db, profile_id, slots, current_url):
    """A third remote IPTV stream must not exceed a two-connection subscription.

    The existing SYN DVR relay handles a currently recorded channel without
    opening an extra upstream connection.
    """
    now = time.time()
    active_or_imminent = [j for j in admitted_jobs(db, profile_id)
                          if j.get('status') == 'running' or
                          float(j.get('start', math.inf)) <= now + 3]
    if any(j.get('url') == current_url for j in active_or_imminent):
        return False
    return len(active_or_imminent) >= int(slots)
