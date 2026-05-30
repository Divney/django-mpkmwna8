from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from homepage.slideshow_sources import slideshow_video_urls


def index(request):
    if request.user.is_authenticated:
        return redirect('slideshow')
    return redirect('login')


@login_required
def slideshow(request):
    return render(
        request,
        'homepage/slideshow.html',
        {'video_urls': slideshow_video_urls()},
    )
