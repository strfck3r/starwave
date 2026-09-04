#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate unified StarWave EPG from live upstream feeds (Roku and Samsung TV Plus).

Downloads live EPG feeds from i.mjh.nz, prefixes channel IDs to match channels.m3u8
(roku_* and samsung_*), and writes docs/iptv/epg.xml and docs/iptv/epg.xml.gz.
"""

import datetime
import gzip
import os
import re
import sys
import time
import urllib.request
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import epg_health

ROKU_EPG_URL = 'https://i.mjh.nz/Roku/all.xml.gz'
SAMSUNG_EPG_URL = 'https://i.mjh.nz/SamsungTVPlus/all.xml.gz'

# Ceilings on what a third-party response may cost us, measured 2026-09-04 by HEAD
# against the live feeds: Roku 3.18 MB compressed, Samsung 2.67 MB. The merged,
# playlist-filtered result is 16.3 MB uncompressed.
#
# Without these, `gzip.decompress(r.read())` is unbounded twice over: the response body
# is read whole into memory, and a gzip stream can expand by ~1000x, so a few megabytes
# of hostile or corrupt input can exhaust the runner. This job runs unattended every
# three hours against a host nobody here controls.
MAX_FEED_COMPRESSED = 64 * 1024 * 1024     # ~20x the largest observed feed
MAX_FEED_DECOMPRESSED = 512 * 1024 * 1024  # ~13x a generous estimate of either feed


class EpgUnfit(RuntimeError):
    """Raised when a freshly built EPG fails its fitness checks and must not be promoted."""


def fetch_gz(url):
    """Download and inflate a gzipped feed under hard size ceilings.

    Three ways a third-party host can hand us a short feed, and what happens to each:

    * OVERSIZED BODY. The response is read one byte past the compressed ceiling, so
      too much data is detected rather than silently truncated into a short feed -
      which the fitness checks would then reject, but for the wrong stated reason.
    * DECOMPRESSION BOMB. decompressobj with an explicit max_length, not
      gzip.decompress: the latter has no output bound, so a bomb is only caught
      after it has been allocated.
    * TRUNCATED STREAM - a dropped connection mid-download. This is the one that
      does NOT announce itself. gzip.decompress raised EOFError; decompressobj
      returns the partial data and merely leaves .eof False, so the caller has to
      look. Measured against the shipped 17.1 MB artifact: a body cut to 99% still
      inflated to 798 channels and 29,582 programmes, clearing MIN_CHANNELS,
      MIN_PROGRAMMES and every coverage floor - a partially dark guide that would
      pass the whole gate. Even the 60% cut cleared MIN_PROGRAMMES. So .eof is
      checked and a short stream is refused here, where the cause is still known.

    Multi-member gzip is legal and CDNs emit it. gzip.decompress concatenates the
    members; decompressobj stops after the first and parks the remainder in
    .unused_data, which would drop real data with no error at all. Each member is
    inflated in turn, against one shared output budget, so the result matches the
    call this replaced. Trailing bytes that are not a further member still refuse the
    feed, as they did before - a zlib.error here where gzip raised BadGzipFile; both
    reach __main__ as EPG_STATUS: ERROR, exit 3.
    """
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read(MAX_FEED_COMPRESSED + 1)
    if len(raw) > MAX_FEED_COMPRESSED:
        raise RuntimeError('%s sent more than %d compressed bytes'
                           % (url, MAX_FEED_COMPRESSED))
    members = []
    total = 0
    while raw:
        dec = zlib.decompressobj(16 + zlib.MAX_WBITS)
        out = dec.decompress(raw, MAX_FEED_DECOMPRESSED - total + 1)
        total += len(out)
        # Bomb first: hitting max_length also leaves .eof False, and "too big" is the
        # truer description of that body than "truncated".
        if total > MAX_FEED_DECOMPRESSED:
            raise RuntimeError('%s expands past %d bytes - refusing (decompression bomb)'
                               % (url, MAX_FEED_DECOMPRESSED))
        if not dec.eof:
            raise RuntimeError('%s ended mid-stream after %d compressed bytes - refusing '
                               '(truncated gzip)' % (url, len(raw)))
        members.append(out)
        # NUL padding after a member is legal and gzip.decompress skips it
        # (CPython Lib/gzip.py: `data = do.unused_data[8:].lstrip(b"\x00")`). No
        # [8:] here: that call inflates raw deflate (wbits=-MAX_WBITS) and must step
        # over the 8-byte gzip trailer itself, while 16+MAX_WBITS consumes the
        # trailer as part of the member. Without the lstrip a padded feed would be
        # refused as trailing garbage - fail-closed, but still a regression against
        # the call replaced.
        raw = dec.unused_data.lstrip(b'\x00')
    if not members:
        raise RuntimeError('%s sent an empty body' % url)
    return b''.join(members).decode('utf-8', errors='ignore')


def _write_atomic(path, write_body):
    """Write via a temp file in the same directory, then rename.

    epg.xml and epg.xml.gz are two encodings of one document and the gate asserts they
    are identical. A crash or a full disk partway through a direct write leaves a
    truncated file that is still served, and leaves the pair disagreeing about what the
    guide contains. os.replace is atomic within a filesystem, so a reader sees either
    the old file or the complete new one.
    """
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + '.tmp'
    try:
        write_body(tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def generate_epg(output_xml=None, output_gz=None, playlist_file=None):
    t0 = time.time()
    print('Downloading Roku EPG from %s...' % ROKU_EPG_URL)
    r_xml = fetch_gz(ROKU_EPG_URL)

    print('Downloading Samsung EPG from %s...' % SAMSUNG_EPG_URL)
    s_xml = fetch_gz(SAMSUNG_EPG_URL)

    print('Prefixing channel and programme IDs...')
    r_xml = re.sub(r'<channel id="([^"]+)">', r'<channel id="roku_\1">', r_xml)
    r_xml = re.sub(r'<programme channel="([^"]+)"', r'<programme channel="roku_\1"', r_xml)

    s_xml = re.sub(r'<channel id="([^"]+)">', r'<channel id="samsung_\1">', s_xml)
    s_xml = re.sub(r'<programme channel="([^"]+)"', r'<programme channel="samsung_\1"', s_xml)

    r_channels = re.findall(r'<channel id="[^"]+">.*?</channel>', r_xml, re.DOTALL)
    s_channels = re.findall(r'<channel id="[^"]+">.*?</channel>', s_xml, re.DOTALL)

    r_programmes = re.findall(r'<programme channel="[^"]+".*?</programme>', r_xml, re.DOTALL)
    s_programmes = re.findall(r'<programme channel="[^"]+".*?</programme>', s_xml, re.DOTALL)

    # Filter by playlist if playlist_file is given
    if playlist_file and os.path.exists(playlist_file):
        with open(playlist_file, 'r', encoding='utf-8') as f:
            pl_text = f.read()
        target_ids = set(re.findall(r'tvg-id="([^"]+)"', pl_text))
        all_channels = [c for c in (r_channels + s_channels) if any(('id="%s"' % tid) in c for tid in target_ids)]
        all_programmes = [p for p in (r_programmes + s_programmes) if any(('channel="%s"' % tid) in p for tid in target_ids)]
    else:
        all_channels = r_channels + s_channels
        all_programmes = r_programmes + s_programmes

    # Stamp the build time into the artifact. Freshness checks downstream read this
    # rather than guessing from programme times or from a file mtime that a git
    # checkout resets.
    built_at = datetime.datetime.now(datetime.timezone.utc)
    xml_lines = ['<?xml version="1.0" encoding="utf-8" ?>',
                 '<tv date="%s +0000" generator-info-name="StarWave generate-epg.py">'
                 % built_at.strftime('%Y%m%d%H%M%S')]
    xml_lines.extend(all_channels)
    xml_lines.extend(all_programmes)
    xml_lines.append('</tv>')
    full_xml = '\n'.join(xml_lines)

    # Refuse to promote an unfit build. Before this check the script wrote whatever it
    # got and printed "Complete", so a truncated upstream would silently overwrite a
    # good artifact with one that renders an empty guide - which is how the
    # 2026-09-03 incident stayed invisible until a television showed it.
    metrics, unfit = epg_health.check(full_xml, epg_health.playlist_ids_from(playlist_file))
    print(epg_health.format_report(metrics, unfit))
    if unfit:
        print('REFUSING TO WRITE: the generated EPG is not fit to ship (see UNFIT above).')
        print('Existing artifacts were left untouched.')
        raise EpgUnfit('; '.join(unfit))

    if output_xml:
        def _xml(tmp):
            with open(tmp, 'w', encoding='utf-8') as f:
                f.write(full_xml)
        _write_atomic(output_xml, _xml)
        print('Wrote %s (%d bytes)' % (output_xml, len(full_xml)))

    if output_gz:
        def _gz(tmp):
            with gzip.open(tmp, 'wb') as f:
                f.write(full_xml.encode('utf-8'))
        _write_atomic(output_gz, _gz)
        print('Wrote %s (%d bytes)' % (output_gz, os.path.getsize(output_gz)))

    print('Complete in %.2fs: %d channels, %d programmes' % (time.time() - t0, len(all_channels), len(all_programmes)))
    return full_xml


if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Paths are overridable so ONE copy of this script serves both layouts: the
    # workshop repo (docs/iptv/...) and the public Kodi repo, which carries the same
    # files at iptv/... . Without this the two would need forked copies, and a forked
    # generator is a generator that drifts.
    out_xml = os.environ.get('EPG_OUT_XML') or os.path.join(base_dir, 'docs', 'iptv', 'epg.xml')
    out_gz = os.environ.get('EPG_OUT_GZ') or os.path.join(base_dir, 'docs', 'iptv', 'epg.xml.gz')
    pl_file = os.environ.get('EPG_PLAYLIST') or os.path.join(base_dir, 'docs', 'iptv', 'channels.m3u8')
    # Exit codes are the whole point of running this unattended: 0 only when a fit
    # artifact was actually written. 2 = unfit build refused, 3 = upstream failure.
    # A scheduler that ignores this will keep serving an expired guide in silence.
    try:
        generate_epg(output_xml=out_xml, output_gz=out_gz, playlist_file=pl_file)
    except EpgUnfit as e:
        print('EPG_STATUS: UNFIT - %s' % e, file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print('EPG_STATUS: ERROR - %s: %s' % (type(e).__name__, e), file=sys.stderr)
        sys.exit(3)
    print('EPG_STATUS: OK')
