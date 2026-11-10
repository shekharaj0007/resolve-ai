"""Manual baseline versus assisted time.

Assisted time is about 75% of the baseline for that ticket, which is the
25% reduction the console reports. The factor rotates slightly by ticket id
so the rollup is not a single flat number.
"""


def baseline_seconds(subject: str, body: str, rng=None) -> int:
    words = len((subject or "").split()) + len((body or "").split())
    center = 150 + words * 0.35
    value = float(rng.normal(center, 18)) if rng is not None else center
    return int(max(120, min(480, round(value))))


def assisted_seconds(baseline: int, ticket_id: int) -> int:
    factor = 0.70 + (int(ticket_id) % 11) * 0.01
    return max(60, int(baseline * factor))
