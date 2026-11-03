"""Parse YouTube watch / share / embed URLs into an 11-character video id."""
import re
from urllib.parse import parse_qs, urlparse

_YOUTUBE_HOSTS = {
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
    'music.youtube.com',
    'youtu.be',
    'www.youtu.be',
    'youtube-nocookie.com',
    'www.youtube-nocookie.com',
}

_ID_RE = re.compile(r'^[A-Za-z0-9_-]{11}$')


def extract_youtube_id(value):
    raw = (value or '').strip()
    if not raw:
        return None
    if _ID_RE.fullmatch(raw):
        return raw

    parsed = urlparse(raw if '://' in raw else f'https://{raw}')
    host = (parsed.hostname or '').lower()
    if host not in _YOUTUBE_HOSTS:
        return None

    if host.endswith('youtu.be'):
        candidate = parsed.path.strip('/').split('/')[0]
        return candidate if _ID_RE.fullmatch(candidate) else None

    path = parsed.path or ''
    parts = [part for part in path.split('/') if part]
    if parts:
        if parts[0] in {'embed', 'shorts', 'live', 'v'} and len(parts) >= 2:
            candidate = parts[1]
            return candidate if _ID_RE.fullmatch(candidate) else None
        if parts[0] == 'watch':
            query = parse_qs(parsed.query)
            candidate = (query.get('v') or [None])[0]
            return candidate if candidate and _ID_RE.fullmatch(candidate) else None

    query = parse_qs(parsed.query)
    candidate = (query.get('v') or [None])[0]
    return candidate if candidate and _ID_RE.fullmatch(candidate) else None
