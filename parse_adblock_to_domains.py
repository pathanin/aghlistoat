#!/usr/bin/env python3
# parse_adblock_to_domains.py
import sys, re, argparse
from urllib.parse import urlparse

SEP_RE = re.compile(r'[\^/:%\*\?\|]')  # separators that end a hostname in ABP syntax
HOST_RE = re.compile(r'^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z0-9\-]{2,63}$')
IP_RE = re.compile(r'^(?:\d{1,3}\.){3}\d{1,3}$')

def looks_like_host(s: str) -> bool:
    if not s: return False
    s = s.strip('.').lower()
    if s.endswith('.'): s = s[:-1]
    if len(s) == 0 or s.count('.') < 1: return False
    if not re.fullmatch(r'[a-z0-9\.\-]+', s): return False
    return bool(HOST_RE.match(s))

def netloc_host(s: str) -> str | None:
    try:
        if '://' not in s: s = 'http://' + s  # urlparse needs a scheme
        h = urlparse(s).hostname
        if h and looks_like_host(h): return h.lower()
    except Exception:
        pass
    return None

def extract_from_abp(line: str) -> str | None:
    s = line.strip()
    if not s: return None
    if s.startswith('!') or s.startswith('['): return None              # comments/headers
    if s.startswith('@@'): return None                                   # exceptions
    if '##' in s or '#@#' in s or '#?#' in s: return None                # cosmetic
    if s.startswith('/') and s.endswith('/') and len(s) > 2: return None # regex rule

    # Hosts file formats: "0.0.0.0 domain ..." or "127.0.0.1 domain"
    parts = s.split()
    if len(parts) >= 2 and IP_RE.match(parts[0]):
        # emit each token that looks like a host
        for tok in parts[1:]:
            tok = tok.strip()
            if looks_like_host(tok):
                return tok.lower()
        return None

    # ||example.com^ ...
    if s.startswith('||'):
        s2 = s[2:]
        s2 = s2.lstrip('.')
        host = SEP_RE.split(s2, 1)[0].strip('.').lower()
        return host if looks_like_host(host) else None

    # |http(s)://... or full URLs anywhere
    if s.startswith('|'):
        s2 = s[1:]
        if '://' in s2:
            h = netloc_host(s2)
            return h
        # anchored but no scheme
        host = SEP_RE.split(s2, 1)[0].lstrip('.').strip('.').lower()
        return host if looks_like_host(host) else None

    if s.startswith('http://') or s.startswith('https://') or '://' in s:
        return netloc_host(s)

    # Generic pattern, possibly with wildcards or separators
    s2 = s
    s2 = s2.replace('*.', '.')  # collapse common wildcard prefix
    s2 = s2.lstrip('*.|')
    host = SEP_RE.split(s2, 1)[0].strip('.').lower()
    return host if looks_like_host(host) else None

def main():
    ap = argparse.ArgumentParser(description="Convert Adblock-style list to domain-only list for Pi-hole.")
    ap.add_argument('file', nargs='?', default='-',
                    help="Input file (default: stdin)")
    ap.add_argument('--keep-subdomains', action='store_true',
                    help="Do not collapse subdomains to their exact form (default already keeps them).")
    ap.add_argument('--sort', action='store_true',
                    help="Sort output alphabetically.")
    args = ap.parse_args()

    seen = set()
    add = seen.add

    def feed_line(line: str):
        # Allow multiple domains from hosts-format lines
        # Do a light pass to capture all tokens that look like hosts if first token is an IP
        parts = line.strip().split()
        if len(parts) >= 2 and IP_RE.match(parts[0]):
            for tok in parts[1:]:
                if looks_like_host(tok) and tok.lower() not in seen:
                    add(tok.lower())
            return
        host = extract_from_abp(line)
        if host and host not in seen:
            add(host)

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
