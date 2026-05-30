from django.contrib import admin

from homepage.models import Favorite, Video


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('catalog_index', 'filename', 's3_key')
    search_fields = ('filename',)
    ordering = ('catalog_index',)


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ('user', 'video', 'created_at')
    list_filter = ('user',)
    raw_id_fields = ('video',)
