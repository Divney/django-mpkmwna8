from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings

from homepage.catalog import (
    import_catalog_from_videos_txt,
    jump_to_similar_available,
    load_top_neighbors,
    sync_local_catalog_from_folder,
)
from homepage.models import Favorite, Video


class CatalogTests(TestCase):
    def test_import_catalog_from_videos_txt(self):
        count = import_catalog_from_videos_txt()
        self.assertEqual(count, 2236)
        self.assertEqual(Video.objects.count(), 2236)
        video = Video.objects.get(catalog_index=73)
        self.assertTrue(video.filename.endswith('.mp4'))
        self.assertIn('app/videos/', video.s3_key)


class TopNeighborsTests(TestCase):
    def test_top_neighbors_file_shape(self):
        neighbors = load_top_neighbors()
        self.assertIsNotNone(neighbors)
        self.assertEqual(len(neighbors), 2236)
        self.assertEqual(len(neighbors[73]), 6)
        self.assertNotIn(73, neighbors[73])

    def test_jump_to_similar_available_with_full_catalog(self):
        import_catalog_from_videos_txt()
        self.assertTrue(jump_to_similar_available(2236))
        self.assertFalse(jump_to_similar_available(10))


@override_settings(SLIDESHOW_USE_S3=False)
class LocalCatalogTests(TestCase):
    def test_sync_empty_folder_clears_catalog(self):
        sync_local_catalog_from_folder()
        self.assertEqual(Video.objects.count(), 0)


class FavoritesApiTests(TestCase):
    def setUp(self):
        import_catalog_from_videos_txt()
        self.user = User.objects.create_user(username='tester', password='pass')
        self.client = Client()
        self.client.login(username='tester', password='pass')

    def test_toggle_favorite(self):
        video = Video.objects.get(catalog_index=5)
        response = self.client.post(
            '/api/favorites/toggle/',
            data='{"catalog_index": 5}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['favorited'])
        self.assertTrue(Favorite.objects.filter(user=self.user, video=video).exists())

        response = self.client.post(
            '/api/favorites/toggle/',
            data='{"catalog_index": 5}',
            content_type='application/json',
        )
        self.assertFalse(response.json()['favorited'])
        self.assertFalse(Favorite.objects.filter(user=self.user, video=video).exists())

    def test_video_url_requires_login(self):
        client = Client()
        response = client.get('/api/videos/0/url/')
        self.assertEqual(response.status_code, 302)
