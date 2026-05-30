from pathlib import Path

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings


def slideshow_video_urls():
    if settings.SLIDESHOW_USE_S3:
        return _s3_slideshow_video_urls()
    return _local_slideshow_video_urls()


def slideshow_storage_status():
    if settings.SLIDESHOW_USE_S3:
        return _s3_storage_status()
    return _local_storage_status()


def _local_slideshow_video_urls():
    video_dir = Path(settings.SLIDESHOW_VIDEOS_DIR)
    if not video_dir.is_dir():
        return []

    urls = []
    for path in sorted(video_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in settings.SLIDESHOW_VIDEO_EXTENSIONS:
            urls.append(f'{settings.MEDIA_URL}{path.name}')
    return urls


def _local_storage_status():
    video_dir = Path(settings.SLIDESHOW_VIDEOS_DIR)
    if not video_dir.is_dir():
        return {
            'backend': 'local',
            'ok': False,
            'message': f'Directory not found: {video_dir}',
            'video_count': 0,
        }

    count = sum(
        1
        for path in video_dir.iterdir()
        if path.is_file() and path.suffix.lower() in settings.SLIDESHOW_VIDEO_EXTENSIONS
    )
    return {
        'backend': 'local',
        'ok': True,
        'message': f'Using local directory {video_dir}',
        'video_count': count,
    }


def _s3_client():
    return boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)


def _normalized_prefix():
    prefix = settings.AWS_S3_SLIDESHOW_PREFIX.strip('/')
    return f'{prefix}/' if prefix else ''


def _s3_slideshow_video_urls():
    client = _s3_client()
    prefix = _normalized_prefix()
    paginator = client.get_paginator('list_objects_v2')
    urls = []

    for page in paginator.paginate(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Prefix=prefix,
    ):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('/') or not Path(key).suffix:
                continue
            if Path(key).suffix.lower() not in settings.SLIDESHOW_VIDEO_EXTENSIONS:
                continue
            urls.append(
                client.generate_presigned_url(
                    'get_object',
                    Params={
                        'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                        'Key': key,
                    },
                    ExpiresIn=settings.AWS_S3_PRESIGNED_URL_EXPIRY,
                )
            )

    return sorted(urls)


def _s3_storage_status():
    bucket = settings.AWS_STORAGE_BUCKET_NAME
    prefix = _normalized_prefix()
    client = _s3_client()

    try:
        paginator = client.get_paginator('list_objects_v2')
        video_count = 0
        sample_url = None

        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                key = obj['Key']
                if key.endswith('/') or not Path(key).suffix:
                    continue
                if Path(key).suffix.lower() not in settings.SLIDESHOW_VIDEO_EXTENSIONS:
                    continue
                video_count += 1
                if sample_url is None:
                    sample_url = client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': bucket, 'Key': key},
                        ExpiresIn=settings.AWS_S3_PRESIGNED_URL_EXPIRY,
                    )

        return {
            'backend': 's3',
            'ok': True,
            'message': f's3://{bucket}/{prefix}',
            'video_count': video_count,
            'sample_url': sample_url,
        }
    except (BotoCoreError, ClientError) as exc:
        return {
            'backend': 's3',
            'ok': False,
            'message': str(exc),
            'video_count': 0,
        }
