#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fitness checks for the StarWave EPG artifact.

ONE definition of "is this EPG fit to ship", imported by both sides so they can
never disagree:

  - scripts/generate-epg.py  calls it BEFORE promoting a freshly built file, so a
    truncated upstream can never overwrite a good artifact and still print success.
  - scripts/test-epg.py      calls it in the QA gate, so an expired artifact is
    caught here rather than by a television.

WHY THE THRESHOLDS ARE PER-SOURCE
Measured 2026-09-03 against the live upstreams: Roku publishes ~69h of forward
programme data, Samsung TV Plus publishes ~5h. A single global freshness rule is
therefore meaningless - it is either so loose that 512 dark Samsung channels pass,
or so tight that the gate is red within six hours of every regeneration.

WHY max(stop) IS NOT USED AS A FRESHNESS SIGNAL
The artifact that caused the 2026-09-03 empty-guide incident had a latest stop
2.5h in the FUTURE while 780 of its 799 channels had been dark for 65 hours. A
check on the outermost stop time reports that file as healthy. Coverage is
therefore always measured per channel, and reported as a fraction of the playlist.
"""

import collections
import datetime
import gzip
import os
import re

# --- thresholds, all derived from measurement rather than taste ----------------------
# Floors sit well under the observed values so they catch a broken upstream, not noise.
MIN_CHANNELS = 750           # observed 796-798 against a 799-entry playlist
MIN_PROGRAMMES = 20000       # observed 29,516-29,772
SOURCE_MIN_HORIZON_H = {     # hours of forward coverage each source must supply at build time
    'roku': 24.0,            # observed min 61.7h
    'samsung': 3.0,          # observed min 4.9h - this source is inherently short-horizon
}
# Fraction of playlist channels that must have programme data covering "now".
# Roku alone is ~36% of the playlist and carries ~69h, so a healthy artifact stays
# above this for roughly three days; the incident artifact scored 0.024.
LIVE_COVERAGE_MIN_FRAC = 0.25

# Fraction of EACH SOURCE's playlist channels that must be covering "now".
#
# WHY A WHOLE-ARTIFACT FLOOR IS NOT ENOUGH - both cases measured 2026-09-03/04:
#
#   1. AGEING. Roku is 286/799 of the playlist and carries ~69h; Samsung is 513/799
#      and carries ~4.9h. Roku alone scores 286/799 = 35.8%, which clears a 25%
#      whole-artifact floor on its own. Sweeping the real shipped artifact forward,
#      the 25% rule reported "fit to ship" continuously from hour 0 to hour 68 -
#      including hours 6-68, where Samsung was 0/513 and two thirds of the guide was
#      blank. It first went red at hour 69, when Roku finally expired too.
#
#   2. BUILD-TIME BYPASS. A source whose programmes all START in the future has a
#      long build horizon (the metric measures the distance to the far edge) and zero
#      live coverage. A synthetic with Samsung running build+4h..build+9h reads a
#      9.0h horizon against a 3.0h floor and 35.8% whole-artifact coverage against a
#      25% floor: "fit to ship", with 512 of 798 channels blank the instant it ships.
#
# Both are the same hole: one source can be entirely dark while the artifact passes.
# The denominator is therefore per source, so no source can hide behind another.
#
# THE VALUE. Measured falloff of the real artifact, Samsung live coverage by age:
# 99.8% flat from 0.0h to 4.5h, then 84.0% at 5.0h, 37.2% at 5.5h, 11.5% at 6.0h.
# It is a cliff, not a slope, because every Samsung channel shares one horizon - so
# any floor between ~40% and ~95% trips within about 30 minutes of any other. 0.50
# sits in the middle of that indifference band: far below the 99.8% healthy plateau,
# so ordinary per-channel gaps never trip it, and far above the 11.5% floor of the
# dark state. Measured against the real shipped artifact it trips at 5.2h of age,
# which is 1.7x the workflow's 3-hourly cadence - enough margin for GitHub's
# scheduled-run delays, and short enough that a stalled refresh is caught the same
# day rather than three days later.
#
# OPERATIONAL CONSEQUENCE, stated rather than tuned away: scripts/test-epg.py gates
# the COMMITTED artifact against wall-clock time, so the QA suite goes red 5.2h after
# a hand regeneration. That is a true red, not a false one - at 5.2h the committed
# file really does render two thirds of the guide blank - and the remedy is one
# command. The whole-artifact rule already had this property; it fired at 69h, which
# is why the incident reached a television first.
SOURCE_LIVE_MIN_FRAC = 0.50

_PROG_RE = re.compile(r'<programme channel="([^"]+)" start="([^"]+)" stop="([^"]+)"')
_CHAN_RE = re.compile(r'<channel id="([^"]+)"')
_TVGID_RE = re.compile(r'tvg-id="([^"]+)"')
_TVDATE_RE = re.compile(r'<tv[^>]*\sdate="([^"]+)"')


def _ts(value):
    """Parse an XMLTV timestamp to a naive UTC datetime.

    XMLTV stamps look like '20260904044800 +0000'. The offset is parsed rather than
    assumed: a source that starts emitting local time would otherwise shift every
    programme silently.
    """
    value = value.strip()
    base = datetime.datetime.strptime(value[:14], '%Y%m%d%H%M%S')
    m = re.search(r'([+-])(\d{2})(\d{2})\s*$', value)
    if m:
        sign = 1 if m.group(1) == '+' else -1
        offset = datetime.timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
        base -= sign * offset
    return base


def read_xml(path):
    """Read an EPG artifact, transparently handling .gz."""
    if path.endswith('.gz'):
        with gzip.open(path, 'rb') as f:
            return f.read().decode('utf-8', errors='replace')
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def measure(xml_text, playlist_ids=None, now=None):
    """Reduce an EPG document to the numbers the checks are made of."""
    now = now or datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    channels = _CHAN_RE.findall(xml_text)
    programmes = _PROG_RE.findall(xml_text)

    first = {}   # channel id -> earliest programme start
    last = {}    # channel id -> latest programme stop
    for cid, start, stop in programmes:
        try:
            s, e = _ts(start), _ts(stop)
        except (ValueError, IndexError):
            continue
        if cid not in first or s < first[cid]:
            first[cid] = s
        if cid not in last or e > last[cid]:
            last[cid] = e

    # Build time is READ from the artifact, never inferred. XMLTV's <tv date="...">
    # carries it, and generate-epg.py stamps it on every file it writes.
    #
    # Inference was tried first and rejected: taking the latest per-channel earliest
    # start overshot the true build time by 2.7h on a freshly built file, because some
    # channels' first listed programme begins in the future. That understated Samsung's
    # horizon by more than half and would have failed a perfectly good artifact. An
    # artifact that states its own build time needs no estimator.
    stamped = _TVDATE_RE.search(xml_text)
    built_at = None
    if stamped:
        try:
            built_at = _ts(stamped.group(1))
        except (ValueError, IndexError):
            built_at = None

    horizon = {}  # source prefix -> worst-case forward coverage supplied at build time
    by_source = collections.defaultdict(list)
    for cid, end in last.items():
        by_source[cid.split('_', 1)[0]].append(end)
    if built_at:
        for source, ends in by_source.items():
            ends = sorted(ends)
            # 5th percentile, not min: one malformed entry should not condemn a source.
            p05 = ends[int(0.05 * len(ends))]
            horizon[source] = (p05 - built_at).total_seconds() / 3600.0

    covering_now = {cid for cid, end in last.items() if first[cid] <= now <= end}
    playlist_ids = set(playlist_ids or [])
    if playlist_ids:
        live_frac = len(covering_now & playlist_ids) / float(len(playlist_ids))
        unmatched = sorted(set(channels) - playlist_ids)
    else:
        live_frac = (len(covering_now) / float(len(channels))) if channels else 0.0
        unmatched = []

    # Per-source live coverage. The denominator is the source's share of the PLAYLIST
    # when one is supplied - that is what a device actually asks for, and it counts a
    # channel the playlist wants but the artifact omits as dark rather than absent.
    # With no playlist, fall back to the source's channels in the document.
    denom_ids = playlist_ids or set(channels)
    live_by_source = {}
    source_size = collections.Counter()
    for cid in denom_ids:
        source_size[cid.split('_', 1)[0]] += 1
    for source, size in source_size.items():
        live = sum(1 for cid in covering_now
                   if cid in denom_ids and cid.split('_', 1)[0] == source)
        live_by_source[source] = {'live': live, 'of': size, 'frac': live / float(size)}

    return {
        'now': now,
        'built_at': built_at,
        'channels': len(channels),
        'channel_ids': set(channels),
        'programmes': len(programmes),
        'sources': {s: len(v) for s, v in by_source.items()},
        'horizon_h': horizon,
        'covering_now': len(covering_now & playlist_ids) if playlist_ids else len(covering_now),
        'live_frac': live_frac,
        'live_by_source': live_by_source,
        'unmatched_ids': unmatched,
        'playlist_size': len(playlist_ids),
    }


def check(xml_text, playlist_ids=None, now=None, min_channels=None, min_programmes=None,
          live_frac_floor=None, horizons=None, source_live_floor=None):
    """Return (metrics, failures). An empty failure list means fit to ship.

    The floors are overridable so a test can exercise one rule at a time without
    having to satisfy every other rule first; production callers pass none of them.
    """
    min_channels = MIN_CHANNELS if min_channels is None else min_channels
    min_programmes = MIN_PROGRAMMES if min_programmes is None else min_programmes
    live_frac_floor = LIVE_COVERAGE_MIN_FRAC if live_frac_floor is None else live_frac_floor
    horizons = SOURCE_MIN_HORIZON_H if horizons is None else horizons
    source_live_floor = (SOURCE_LIVE_MIN_FRAC if source_live_floor is None
                         else source_live_floor)

    m = measure(xml_text, playlist_ids=playlist_ids, now=now)
    bad = []

    if m['channels'] < min_channels:
        bad.append('only %d channels, floor is %d - upstream is truncated'
                   % (m['channels'], min_channels))
    if m['programmes'] < min_programmes:
        bad.append('only %d programmes, floor is %d - upstream is truncated'
                   % (m['programmes'], min_programmes))

    # A silently mismatched prefix set yields a full-looking file and an empty guide,
    # because Kodi matches tvg-id to <channel id> by exact string.
    for source in horizons:
        if not m['sources'].get(source):
            bad.append('no channels carry the "%s_" prefix - the ID prefixing step '
                       'did not run or the upstream layout changed' % source)
    stray = sorted(s for s in m['sources'] if s not in horizons)
    if stray:
        bad.append('unexpected channel-ID prefixes %s - these cannot match channels.m3u8'
                   % (stray,))
    if playlist_ids and m['unmatched_ids']:
        bad.append('%d channel IDs are absent from channels.m3u8 (e.g. %s) - they will '
                   'render as empty rows' % (len(m['unmatched_ids']), m['unmatched_ids'][:3]))

    # Forward coverage supplied at BUILD time. Time-invariant, so this catches an
    # upstream that started serving a short window without going red as the file ages.
    # Only enforceable on a stamped artifact; a file predating the stamp is reported
    # as unstamped rather than judged against a guess.
    if m['built_at'] is None:
        m['horizon_note'] = ('artifact carries no <tv date="..."> stamp, so build-time '
                             'horizon was not checked; it was written by a generator '
                             'older than 2026-09-03')
    for source, floor in horizons.items():
        got = m['horizon_h'].get(source)
        if got is None:
            continue
        if got < floor:
            bad.append('%s supplied only %.1fh of forward coverage at build time, floor '
                       'is %.1fh - the feed was short, not the schedule' % (source, got, floor))

    # Wall-clock: is this artifact actually lighting up a guide right now?
    if m['live_frac'] < live_frac_floor:
        bad.append('only %d of %d playlist channels (%.1f%%) have programme data covering '
                   'now, floor is %.0f%% - this artifact renders an empty guide. '
                   'Regenerate with: python3 scripts/generate-epg.py'
                   % (m['covering_now'], m['playlist_size'] or m['channels'],
                      100 * m['live_frac'], 100 * live_frac_floor))

    # Wall-clock, PER SOURCE. The rule above is a whole-artifact average, and an average
    # cannot see one source going dark behind another: Roku alone is 35.8% of the
    # playlist, so it clears a 25% average by itself while all 513 Samsung channels are
    # blank. Enforced only for the sources this file knows about; an unexpected prefix
    # is already a failure under the "stray prefixes" rule above.
    for source in sorted(horizons):
        stat = m['live_by_source'].get(source)
        if not stat or not stat['of']:
            continue  # absent source is caught by the prefix rule, with a better message
        if stat['frac'] < source_live_floor:
            bad.append('source "%s" has only %d of its %d playlist channels (%.1f%%) '
                       'covering now, per-source floor is %.0f%% - this source is dark '
                       'and the whole-artifact average is hiding it. '
                       'Regenerate with: python3 scripts/generate-epg.py'
                       % (source, stat['live'], stat['of'], 100 * stat['frac'],
                          100 * source_live_floor))

    return m, bad


def playlist_ids_from(path):
    if not path or not os.path.exists(path):
        return set()
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        return set(_TVGID_RE.findall(f.read()))


def format_report(m, bad):
    lines = ['EPG health:',
             '  built at        %s UTC' % (m['built_at'] or 'unknown'),
             '  channels        %d  %s' % (m['channels'], dict(sorted(m['sources'].items()))),
             '  programmes      %d' % m['programmes'],
             '  build horizon   %s%s' % ({k: round(v, 1) for k, v in sorted(m['horizon_h'].items())},
                                         '' if m['built_at'] else '  (not checked - unstamped)'),
             '  covering now    %d/%d (%.1f%%)' % (m['covering_now'],
                                                   m['playlist_size'] or m['channels'],
                                                   100 * m['live_frac']),
             '  ...per source   %s' % ', '.join(
                 '%s %d/%d (%.1f%%)' % (s, v['live'], v['of'], 100 * v['frac'])
                 for s, v in sorted(m.get('live_by_source', {}).items()))]
    for b in bad:
        lines.append('  UNFIT: %s' % b)
    if not bad:
        lines.append('  verdict: fit to ship')
    return '\n'.join(lines)
