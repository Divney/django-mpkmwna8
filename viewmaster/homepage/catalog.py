import json
from pathlib import Path

from django.conf import settings
from django.db import transaction

from homepage.models import Video


def data_dir():
    return Path(settings.VIEWMASTER_DATA_DIR)


def videos_txt_path():
    return data_dir() / 'videos.txt'


def load_videos_txt_lines():
    lines = videos_txt_path().read_text(encoding='utf-8').splitlines()
    return [line.strip() for line in lines if line.strip().endswith('.mp4')]


def load_similarity_order(filename):
    path = data_dir() / filename
    return json.loads(path.read_text(encoding='utf-8'))


def expected_catalog_size():
    return len(load_videos_txt_lines())


def similarity_orders_available(video_count):
    if video_count == 0:
        return False
    try:
        most = load_similarity_order('most_similar.json')
        least = load_similarity_order('least_similar.json')
    except (OSError, json.JSONDecodeError):
        return False
    return len(most) == video_count and len(least) == video_count


def filter_similarity_order(order, video_count):
    return [index for index in order if 0 <= index < video_count]


def get_similarity_orders_for_client(video_count):
    if not similarity_orders_available(video_count):
        return None, None
    most = filter_similarity_order(load_similarity_order('most_similar.json'), video_count)
    least = filter_similarity_order(load_similarity_order('least_similar.json'), video_count)
    return most, least


def load_top_neighbors():
    path = data_dir() / 'top_neighbors.json'
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding='utf-8'))


def jump_to_similar_available(video_count):
    if video_count == 0:
        return False
    expected = expected_catalog_size()
    if video_count != expected:
        return False
    neighbors = load_top_neighbors()
    if not neighbors or len(neighbors) != video_count:
        return False
    return all(len(row) == 6 for row in neighbors)


def get_top_neighbors_for_client(video_count):
    if not jump_to_similar_available(video_count):
        return None
    return load_top_neighbors()


@transaction.atomic
def import_catalog_from_videos_txt():
    filenames = load_videos_txt_lines()
    prefix = settings.AWS_S3_VIDEO_KEY_PREFIX.rstrip('/')
    Video.objects.all().delete()
    Video.objects.bulk_create(
        [
            Video(
                catalog_index=index,
                filename=filename,
                s3_key=f'{prefix}/{filename}',
            )
            for index, filename in enumerate(filenames)
        ],
        batch_size=500,
    )
    return len(filenames)


@transaction.atomic
def sync_local_catalog_from_folder():
    video_dir = Path(settings.SLIDESHOW_VIDEOS_DIR)
    if not video_dir.is_dir():
        Video.objects.all().delete()
        return 0

    filenames = sorted(
        path.name
        for path in video_dir.iterdir()
        if path.is_file() and path.suffix.lower() in settings.SLIDESHOW_VIDEO_EXTENSIONS
    )
    Video.objects.all().delete()
    Video.objects.bulk_create(
        [
            Video(catalog_index=index, filename=filename, s3_key='')
            for index, filename in enumerate(filenames)
        ],
        batch_size=500,
    )
    return len(filenames)


def ensure_catalog_loaded():
    if settings.SLIDESHOW_USE_S3:
        if not Video.objects.exists():
            import_catalog_from_videos_txt()
    else:
        sync_local_catalog_from_folder()


def get_video_by_catalog_index(catalog_index):
    return Video.objects.filter(catalog_index=catalog_index).first()
