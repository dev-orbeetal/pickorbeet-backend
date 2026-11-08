"""Serve the exported PickOrbeet admin panel at the site root."""
import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect


PLACEHOLDER_PAGES = {
    'products': Path('products') / '_' / 'index.html',
    'orders': Path('orders') / '_' / 'index.html',
}


def _inside(root, candidate):
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return True


def _html(path):
    return FileResponse(path.open('rb'), content_type='text/html; charset=utf-8')


def redirect_legacy_admin(request, path=''):
    """Send the old /admin/finance/ address to /finance/."""
    cleaned = '/'.join(
        part for part in path.split('/') if part and part not in ('.', '..')
    )
    target = f'/{cleaned}/' if cleaned else '/'
    query = request.META.get('QUERY_STRING')
    if query:
        target = f'{target}?{query}'
    return redirect(target, permanent=True)


def serve_admin_panel(request, path=''):
    root = Path(settings.ADMIN_PANEL_DIST).resolve()
    if not (root / 'index.html').is_file():
        return HttpResponse(
            'Admin panel build is missing. From the project root run make up, '
            'or build backend/admin_panel with NEXT_PUBLIC_API_URL=/api/v1.',
            status=503,
            content_type='text/plain; charset=utf-8',
        )

    parts = [part for part in path.split('/') if part and part not in ('.', '..')]
    if len(parts) == 2 and parts[0] in PLACEHOLDER_PAGES and parts[1] != 'new':
        placeholder = (root / PLACEHOLDER_PAGES[parts[0]]).resolve()
        if _inside(root, placeholder) and placeholder.is_file():
            return _html(placeholder)

    candidate = (root.joinpath(*parts)).resolve() if parts else root
    if not _inside(root, candidate):
        return HttpResponse('Not found', status=404, content_type='text/plain; charset=utf-8')

    if candidate.is_dir():
        candidate = candidate / 'index.html'
    if candidate.is_file() and _inside(root, candidate):
        content_type = mimetypes.guess_type(candidate.name)[0] or 'application/octet-stream'
        return FileResponse(candidate.open('rb'), content_type=content_type)

    return HttpResponse('Not found', status=404, content_type='text/plain; charset=utf-8')
