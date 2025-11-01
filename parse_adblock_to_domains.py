#!/usr/bin/env python3
# parse_adblock_to_domains.py
import sys, re, argparse
from urllib.parse import urlparse

SEP_RE = re.compile(r'[\^/:%\*\?\|]')
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

def extract_domain(line: str) -> tuple[str | None, str | None]:
    """
    Returns (domain, status)
    status = 'whitelist' if @@ rule, 'block' if normal rule, None otherwise
    """
    s = BOM_WS_RE.sub('', line.rstrip())
    if not s:
        return None, None
    # skip comments and headers
    if s.startswith(('!', '#', '[')):
        return None, None
    if '##' in s or '#@#' in s or '#?#' in s:
        return None, None
    if '$badfilter' in s or '$rewrite=' in s:
        return None, None
    if s.startswith('/') and s.endswith('/') and len(s) > 2:
        return None, None

    is_whitelist = s.startswith('@@')
    if is_whitelist:
        s = s[2:]  # remove @@ prefix

    # hosts-style lines
    parts = s.split()
    if len(parts) >= 2 and IP_RE.match(parts[0]):
        for tok in parts[1:]:
            if looks_like_host(tok):
                return tok.lower(), 'whitelist' if is_whitelist else 'block'
        return None, None

    # ||example.com^
    if s.startswith('||'):
        s2 = s[2:].lstrip('.')
        host = SEP_RE.split(s2, 1)[0].strip('.').lower()
        return (host, 'whitelist' if is_whitelist else 'block') if looks_like_host(host) else (None, None)

    # |http(s)://
    if s.startswith('|'):
        s2 = s[1:]
        if '://' in s2:
            h = netloc_host(s2)
            return (h, 'whitelist' if is_whitelist else 'block') if h else (None, None)
        host = SEP_RE.split(s2, 1)[0].lstrip('.').strip('.').lower()
        return (host, 'whitelist' if is_whitelist else 'block') if looks_like_host(host) else (None, None)

    if '://' in s:
        h = netloc_host(s)
        return (h, 'whitelist' if is_whitelist else 'block') if h else (None, None)

    # generic patterns
    s2 = s.replace('*.', '.').lstrip('*.|')
    host = SEP_RE.split(s2, 1)[0].strip('.').lower()
    return (host, 'whitelist' if is_whitelist else 'block') if looks_like_host(host) else (None, None)


def main():
    ap = argparse.ArgumentParser(description="Convert Adblock/uBO/hosts lists to domain-only list for Pi-hole.")
    ap.add_argument('file', nargs='?', default='-', help="Input file (default: stdin)")
    ap.add_argument('--sort', action='store_true', help="Sort output alphabetically.")
    args = ap.parse_args()

    blocked = set()
    whitelisted = set()

    def feed_line(line: str):
        domain, status = extract_domain(line)
        if not domain or not status:
            return

        if status == 'whitelist':
            whitelisted.add(domain)
            # remove from blocked if it was added before
            if domain in blocked:
                blocked.remove(domain)
        elif status == 'block':
            # skip if it's whitelisted (earlier or later)
            if domain not in whitelisted:
                blocked.add(domain)

    if args.file == '-':
        for line in sys.stdin:
            feed_line(line)
    else:
        with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                feed_line(line)

    out = sorted(blocked) if args.sort else list(blocked)
    for h in out:
        print(h)

if __name__ == '__main__':
    main()
