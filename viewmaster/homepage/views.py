from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


def _slideshow_image_urls():
    image_dir = Path(settings.SLIDESHOW_IMAGES_DIR)
    if not image_dir.is_dir():
        return []

    urls = []
    for path in sorted(image_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in settings.SLIDESHOW_IMAGE_EXTENSIONS:
            urls.append(f'{settings.MEDIA_URL}{path.name}')
    return urls


def index(request):
    if request.user.is_authenticated:
        return redirect('slideshow')
    return redirect('login')


@login_required
def slideshow(request):
    return render(
        request,
        'homepage/slideshow.html',
        {'image_urls': _slideshow_image_urls()},
    )
