from django.conf import settings
from django.db import models


class Video(models.Model):
    catalog_index = models.PositiveIntegerField(unique=True)
    filename = models.CharField(max_length=255)
    s3_key = models.CharField(max_length=512, blank=True)

    class Meta:
        ordering = ['catalog_index']

    def __str__(self):
        return f'{self.catalog_index}: {self.filename}'

    def save(self, *args, **kwargs):
        if not self.s3_key and self.filename:
            prefix = settings.AWS_S3_VIDEO_KEY_PREFIX.rstrip('/')
            self.s3_key = f'{prefix}/{self.filename}'
        super().save(*args, **kwargs)


class Favorite(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='video_favorites',
    )
    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'video'], name='unique_user_video_favorite'),
        ]

    def __str__(self):
        return f'{self.user_id} ★ {self.video_id}'
