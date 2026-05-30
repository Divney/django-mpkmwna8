from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.templatetags.static import static

from homepage.catalog import (
    ensure_catalog_loaded,
    get_similarity_orders_for_client,
    get_top_neighbors_for_client,
    jump_to_similar_available,
    similarity_orders_available,
)
from homepage.models import Favorite, Video


@login_required
def index(request):
    return redirect('slideshow')


@login_required
def slideshow(request):
    ensure_catalog_loaded()
    video_count = Video.objects.count()
    most_similar, least_similar = get_similarity_orders_for_client(video_count)

    favorite_indices = list(
        Favorite.objects.filter(user=request.user)
        .order_by('video__catalog_index')
        .values_list('video__catalog_index', flat=True)
    )

    viewer_config = {
        'videoCount': video_count,
        'defaultStartIndex': settings.VIEWMASTER_DEFAULT_START_INDEX,
        'favoriteIndices': favorite_indices,
        'mostSimilarOrder': most_similar or [],
        'leastSimilarOrder': least_similar or [],
        'similarityOrdersAvailable': similarity_orders_available(video_count),
        'jumpToSimilarAvailable': jump_to_similar_available(video_count),
        'topNeighbors': get_top_neighbors_for_client(video_count) or [],
        'apiVideoUrlTemplate': '/api/videos/{catalog_index}/url/',
        'apiFavoritesToggle': '/api/favorites/toggle/',
        'staticImgBase': static('homepage/img/'),
    }

    return render(
        request,
        'homepage/slideshow.html',
        {
            'viewer_config': viewer_config,
            'has_videos': video_count > 0,
        },
    )

