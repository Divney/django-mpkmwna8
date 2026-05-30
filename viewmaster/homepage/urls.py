from django.contrib.auth import views as auth_views
from django.urls import path

from . import api, views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', auth_views.LoginView.as_view(template_name='homepage/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('slideshow/', views.slideshow, name='slideshow'),
    path('api/videos/<int:catalog_index>/url/', api.video_playback_url, name='api_video_url'),
    path('api/favorites/', api.favorites_list, name='api_favorites_list'),
    path('api/favorites/toggle/', api.favorites_toggle, name='api_favorites_toggle'),
]
