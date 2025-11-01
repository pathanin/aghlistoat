#!/usr/bin/env python3
# parse_adblock_to_domains.py
import sys, re, argparse
from urllib.parse import urlparse

SEP_RE = re.compile(r'[\^/:%\*\?\|]')  # delimiters ending a hostname
HOST_RE = re.compile(r'^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z0-9\-]{2,63}$')
IP_RE = re.compile(r'^(?:\d{1,3}\.){3}\d{1,3}$')
BOM_WS_RE = re.compile(r'^\ufeff?\s*')  # strip BOM + leading spaces

def looks_like_host(s: str) -> bool:
    if not s:
        return False
    s = s.strip('.').lower()
    if s.endswith('.'):
        s = s[:-1]
    if len(s) == 0 or s.count('.') < 1:
        return False
    if not re.fullmatch(r'[a-z0-9.\-]+', s):
        return False
    return bool(HOST_RE.match(s))

def netloc_host(s: str) -> str | None:
    try:
        if '://' not in s:
            s = 'http://' + s
        h = urlparse(s).hostname
        if h and looks_like_host(h):
            return h.lower()
    except Exception:
        pass
    return None

def extract_from_abp(line: str) -> str | None:
    s = BOM_WS_RE.sub('', line.rstrip())
    if not s:
        return None
    # skip comments / headers / whitelist / non-block rules
    if s.startswith(('!', '#', '[', '@@')):
        return None
    if '##' in s or '#@#' in s or '#?#' in s:
        return None
    if '$badfilter' in s or '$rewrite=' in s:
        return None
    if s.startswith('/') and s.endswith('/') and len(s) > 2:
        return None

    # hosts-file style: "0.0.0.0 domain"
    parts = s.split()
    if len(parts) >= 2 and IP_RE.match(parts[0]):
        for tok in parts[1:]:
            if looks_like_host(tok):
                return tok.lower()
        return None

    # ||example.com^ syntax
    if s.startswith('||'):
        s2 = s[2:].lstrip('.')
        host = SEP_RE.split(s2, 1)[0].strip('.').lower()
        return host if looks_like_host(host) else None

    # |http(s):// anchored or |example.com
    if s.startswith('|'):
        s2 = s[1:]
        if '://' in s2:
            return netloc_host(s2)
        host = SEP_RE.split(s2, 1)[0].lstrip('.').strip('.').lower()
        return host if looks_like_host(host) else None

    # full URLs
    if '://' in s:
        return netloc_host(s)

    # generic patterns
    s2 = s.replace('*.', '.').lstrip('*.|')
    host = SEP_RE.split(s2, 1)[0].strip('.').lower()
    return host if looks_like_host(host) else None

def main():
    ap = argparse.ArgumentParser(description="Convert Adblock/uBO/hosts lists to domain-only list for Pi-hole.")
    ap.add_argument('file', nargs='?', default='-', help="Input file (default: stdin)")
    ap.add_argument('--sort', action='store_true', help="Sort output alphabetically.")
    args = ap.parse_args()

    seen = set()

    def feed_line(line: str):
        s = BOM_WS_RE.sub('', line)
        if not s.strip() or s.lstrip().startswith(('!', '#', '[', '@@')):
            return
        parts = s.strip().split()
        if len(parts) >= 2 and IP_RE.match(parts[0]):
            for tok in parts[1:]:
                if looks_like_host(tok) and tok.lower() not in seen:
                    seen.add(tok.lower())
            return
        host = extract_from_abp(s)
        if host and host not in seen:
            seen.add(host)

    if args.file == '-':
        for line in sys.stdin:
            feed_line(line)
    else:
        with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                feed_line(line)

    out = sorted(seen) if args.sort else list(seen)
    for h in out:
        print(h)

if __name__ == '__main__':
    main()
