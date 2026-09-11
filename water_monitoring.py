#!/usr/bin/env python3
"""Purified water system monitoring for a pharmaceutical plant.

Covers the stages you find between the feed and the pharmaceutical-grade point
of use: pre-treatment, RO, UF, EDI and the purified-water distribution loop.

    - conductivity vs the USP <645> stage-1 limit (temperature-dependent)
    - RO / UF / EDI rejection (salt passage)
    - sanitisation schedule with due/overdue logic
    - simple descriptive stats for a conductivity / temperature trend

Date handling uses datetime.date objects; all helpers are pure +
dependency-free.
"""
from datetime import date
from statistics import mean, pstdev

# USP <645> Table 1 — acceptable conductivity of purified water, stage 1
# measurement, at the measured temperature (micro-siemens/cm). The limit is
# evaluated against the temperature read at the moment of measurement, NOT a
# compensated value.
USP_CONDUCTIVITY_TABLE = [
    (0, 0.6), (5, 0.8), (10, 0.9), (15, 1.0), (20, 1.1), (25, 1.3),
    (30, 1.4), (35, 1.5), (40, 1.7), (45, 1.8), (50, 2.1), (55, 2.2),
    (60, 2.4), (65, 2.5), (70, 2.7), (75, 2.9), (80, 3.1), (85, 3.3),
    (90, 3.6), (95, 3.8), (100, 4.1),
]


def usp_conductivity_limit(temp_c):
    """USP <645> stage-1 conductivity limit (uS/cm) at a temperature (C).

    Linearly interpolated between table rows; clamped at the table edges.
    """
    rows = USP_CONDUCTIVITY_TABLE
    if temp_c <= rows[0][0]:
        return rows[0][1]
    if temp_c >= rows[-1][0]:
        return rows[-1][1]
    for i in range(len(rows) - 1):
        t0, c0 = rows[i]
        t1, c1 = rows[i + 1]
        if t0 <= temp_c <= t1:
            return c0 + (c1 - c0) * (temp_c - t0) / (t1 - t0)
    raise ValueError("interpolation failed")


def passes_usp(temp_c, conductivity_us):
    """True if a non-temperature-compensated reading is within the USP limit."""
    if temp_c < 0 or temp_c > 100:
        raise ValueError("temperature outside instrument range 0..100 C")
    if conductivity_us < 0:
        raise ValueError("conductivity cannot be negative")
    return conductivity_us <= usp_conductivity_limit(temp_c)


def rejection_pct(feed_us, product_us):
    """Percent rejection = (1 - product/feed) x 100 for RO/UF/EDI stages."""
    if feed_us <= 0:
        raise ValueError("feed conductivity must be > 0")
    if product_us < 0 or product_us > feed_us:
        raise ValueError("product conductivity must be 0..feed")
    return (1.0 - product_us / feed_us) * 100.0


def salt_passage_pct(feed_us, product_us):
    """Percent salt passage (the complement of rejection)."""
    return 100.0 - rejection_pct(feed_us, product_us)


def _parse(s):
    if isinstance(s, date):
        return s
    return date.fromisoformat(s)


def sanitization_status(last_date, interval_days, today):
    """Due/overdue logic for the sanitisation schedule.

    Returns dict: days_since, next_due (ISO), days_left, status in
    ('overdue', 'due soon', 'in spec', 'done today').
    """
    if interval_days <= 0:
        raise ValueError("sanitisation interval must be > 0 days")
    last = _parse(last_date)
    today = _parse(today)
    if last > today:
        raise ValueError("last sanitisation cannot be in the future")
    days_since = (today - last).days
    days_left = interval_days - days_since
    next_due = last.toordinal() + interval_days
    from datetime import date as _date
    next_due_date = _date.fromordinal(next_due)
    if days_left < 0:
        status = "overdue"
    elif days_left <= 7:
        status = "due soon"
    elif days_since == 0:
        status = "done today"
    else:
        status = "in spec"
    return {"days_since": days_since,
            "next_due": next_due_date.isoformat(),
            "days_left": days_left,
            "status": status}


def series_stats(records):
    """Descriptive stats for (date, temp_c, conductivity_us) records.

    Returns dict with count, mean/max/min of both signals, and the number of
    readings that exceeded the USP stage-1 limit.
    """
    if not records:
        raise ValueError("records cannot be empty")
    temps = [r[1] for r in records]
    conds = [r[2] for r in records]
    exceeded = [(r[0], r[1], r[2], usp_conductivity_limit(r[1]))
                for r in records if not passes_usp(r[1], r[2])]
    return {
        "count": len(records),
        "temp": {"mean": mean(temps), "min": min(temps), "max": max(temps),
                 "stdev": pstdev(temps)},
        "conductivity": {"mean": mean(conds), "min": min(conds),
                         "max": max(conds), "stdev": pstdev(conds)},
        "usp_exceedances": exceeded,
    }


# --- demo data: two weeks of points-of-use loop readings ---
DEMO_READINGS = [
    (date(2026, 8, 25), 25.2, 0.91), (date(2026, 8, 25), 25.1, 0.88),
    (date(2026, 8, 26), 25.4, 0.93), (date(2026, 8, 26), 25.3, 0.90),
    (date(2026, 8, 27), 25.8, 0.95), (date(2026, 8, 27), 25.6, 0.92),
    (date(2026, 8, 28), 26.0, 0.97), (date(2026, 8, 28), 25.9, 0.94),
    (date(2026, 8, 29), 26.2, 0.99), (date(2026, 8, 29), 26.0, 0.95),
    (date(2026, 8, 30), 26.4, 1.02), (date(2026, 8, 30), 26.2, 0.98),
    (date(2026, 8, 31), 26.6, 1.05), (date(2026, 8, 31), 26.4, 1.00),
    (date(2026, 9, 1), 26.9, 1.08), (date(2026, 9, 1), 26.7, 1.04),
    (date(2026, 9, 2), 27.1, 1.10), (date(2026, 9, 2), 26.9, 1.06),
    (date(2026, 9, 3), 27.4, 1.15), (date(2026, 9, 3), 27.2, 1.10),
    (date(2026, 9, 4), 27.8, 1.22), (date(2026, 9, 4), 27.5, 1.16),
    (date(2026, 9, 5), 28.1, 1.28), (date(2026, 9, 5), 27.9, 1.22),
    (date(2026, 9, 6), 28.4, 1.33), (date(2026, 9, 6), 28.1, 1.26),
    (date(2026, 9, 7), 28.6, 1.38), (date(2026, 9, 7), 28.3, 1.30),
    (date(2026, 9, 8), 28.9, 1.42), (date(2026, 9, 8), 28.6, 1.34),
]


if __name__ == "__main__":
    print("Purified water system monitoring")
    print("-" * 50)
    today = date(2026, 9, 9)
    sani = sanitization_status(date(2026, 8, 15), 30, today)
    print(f"Sanitisation: last 2026-08-15, {sani['status'].upper()}, "
          f"{sani['days_left']} days left (next due {sani['next_due']})")
    print()
    for temp, cond in ((25.0, 0.9), (27.0, 1.2), (25.0, 1.45)):
        lim = usp_conductivity_limit(temp)
        ok = passes_usp(temp, cond)
        print(f"  T={temp}C cond={cond} uS/cm  limit={lim:.2f}  "
              f"{'PASS' if ok else 'FAIL <645>'}")
    print()
    print(f"RO rejection: {rejection_pct(420, 6.5):.1f}%")
    print(f"EDI rejection: {rejection_pct(6.5, 0.9):.1f}%")
    print(f"Sanitisation days left: {sani['days_left']}")