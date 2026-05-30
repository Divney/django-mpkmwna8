import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from homepage.catalog import ensure_catalog_loaded, get_video_by_catalog_index
from homepage.models import Favorite, Video
from homepage.slideshow_sources import playback_url_for_video


@login_required
@require_GET
def video_playback_url(request, catalog_index):
    ensure_catalog_loaded()
    video = get_video_by_catalog_index(catalog_index)
    if video is None:
        return JsonResponse({'error': 'Video not found'}, status=404)

    url = playback_url_for_video(video)
    if not url.startswith('http'):
        url = request.build_absolute_uri(url)

    return JsonResponse({'url': url, 'catalog_index': catalog_index, 'filename': video.filename})


@login_required
@require_GET
def favorites_list(request):
    ensure_catalog_loaded()
    indices = list(
        Favorite.objects.filter(user=request.user)
        .select_related('video')
        .order_by('video__catalog_index')
        .values_list('video__catalog_index', flat=True)
    )
    return JsonResponse({'favorites': indices})


@login_required
@require_POST
def favorites_toggle(request):
    ensure_catalog_loaded()
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    catalog_index = payload.get('catalog_index')
    if catalog_index is None:
        return JsonResponse({'error': 'catalog_index required'}, status=400)

    try:
        catalog_index = int(catalog_index)
    except (TypeError, ValueError):
        return JsonResponse({'error': 'catalog_index must be an integer'}, status=400)

    video = get_video_by_catalog_index(catalog_index)
    if video is None:
        return JsonResponse({'error': 'Video not found'}, status=404)

    favorite, created = Favorite.objects.get_or_create(user=request.user, video=video)
    if not created:
        favorite.delete()
        return JsonResponse({'favorited': False, 'catalog_index': catalog_index})

    return JsonResponse({'favorited': True, 'catalog_index': catalog_index})
