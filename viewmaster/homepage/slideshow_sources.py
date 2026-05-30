import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

from homepage.models import Video


def _s3_client():
    return boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)


def playback_url_for_video(video):
    if settings.SLIDESHOW_USE_S3:
        return presigned_url_for_s3_key(video.s3_key)
    return f'{settings.MEDIA_URL}{video.filename}'


def presigned_url_for_s3_key(s3_key):
    client = _s3_client()
    return client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': s3_key,
        },
        ExpiresIn=settings.AWS_S3_PRESIGNED_URL_EXPIRY,
    )


def s3_key_exists(s3_key):
    client = _s3_client()
    try:
        client.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=s3_key)
        return True
    except ClientError:
        return False


def storage_check_status(
    *,
    verbose=False,
    write=None,
    progress_interval=100,
    max_missing_listed=20,
    early_exit_missing=10,
):
    from homepage.catalog import ensure_catalog_loaded

    def log(message):
        if verbose and write:
            write(message)

    backend = 's3' if settings.SLIDESHOW_USE_S3 else 'local'
    log(f'Backend: {backend}')

    if settings.SLIDESHOW_USE_S3:
        log(f'Bucket: s3://{settings.AWS_STORAGE_BUCKET_NAME}/')
        log(f'Region: {settings.AWS_S3_REGION_NAME}')
        log(f'Key prefix: {settings.AWS_S3_VIDEO_KEY_PREFIX}')
    else:
        log(f'Local folder: {settings.SLIDESHOW_VIDEOS_DIR}')

    log('Loading catalog...')
    ensure_catalog_loaded()
    video_count = Video.objects.count()
    log(f'Catalog loaded: {video_count} video(s) in database')

    if settings.SLIDESHOW_USE_S3:
        if video_count == 0:
            return {
                'backend': 's3',
                'ok': False,
                'message': 'Catalog is empty — run import_catalog first',
                'video_count': 0,
                'checked': 0,
                'missing': [],
            }

        log(f'Checking S3 objects ({video_count} keys)...')
        missing = []
        checked = 0
        for video in Video.objects.iterator():
            checked += 1
            if not s3_key_exists(video.s3_key):
                missing.append(video.s3_key)
                if verbose:
                    log(f'  MISSING [{checked}/{video_count}] {video.s3_key}')

            if verbose and (
                checked % progress_interval == 0 or checked == video_count
            ):
                log(
                    f'  Progress: {checked}/{video_count} checked, '
                    f'{len(missing)} missing so far'
                )
            elif not verbose and len(missing) >= early_exit_missing:
                log(
                    f'Stopping early after {early_exit_missing} missing keys '
                    f'({checked}/{video_count} checked). Use verbose mode for a full scan.'
                )
                break

        log('Generating sample presigned URL...')
        sample_video = Video.objects.first()
        sample_url = None
        if sample_video:
            try:
                sample_url = playback_url_for_video(sample_video)
                log(f'Sample key: {sample_video.s3_key}')
            except (BotoCoreError, ClientError) as exc:
                return {
                    'backend': 's3',
                    'ok': False,
                    'message': str(exc),
                    'video_count': video_count,
                    'checked': checked,
                    'missing': missing,
                }

        full_scan = checked == video_count
        ok = video_count > 0 and not missing and full_scan
        message = (
            f's3://{settings.AWS_STORAGE_BUCKET_NAME}/ '
            f'({video_count} catalogued, {checked} checked'
        )
        if not full_scan:
            message += f', scan incomplete — {video_count - checked} not checked'
        message += f', {len(missing)} missing)'
        if missing:
            preview = ', '.join(missing[:3])
            if len(missing) > 3:
                preview += f', ... (+{len(missing) - 3} more)'
            message += f'; examples: {preview}'

        return {
            'backend': 's3',
            'ok': ok,
            'message': message,
            'video_count': video_count,
            'checked': checked,
            'missing': missing,
            'missing_listed': missing[:max_missing_listed],
            'sample_url': sample_url,
        }

    video_dir = settings.SLIDESHOW_VIDEOS_DIR
    ok = video_count > 0
    return {
        'backend': 'local',
        'ok': ok,
        'message': f'Local folder {video_dir} ({video_count} videos)',
        'video_count': video_count,
        'checked': video_count,
        'missing': [],
    }
