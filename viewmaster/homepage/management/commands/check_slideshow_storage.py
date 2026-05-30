from django.core.management.base import BaseCommand

from homepage.slideshow_sources import slideshow_storage_status


class Command(BaseCommand):
    help = 'Verify slideshow video storage (local directory or S3).'

    def handle(self, *args, **options):
        status = slideshow_storage_status()
        backend = status['backend']

        if status['ok']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'OK ({backend}): {status["message"]} — {status["video_count"]} video(s)'
                )
            )
            sample_url = status.get('sample_url')
            if sample_url:
                self.stdout.write(f'Sample URL: {sample_url}')
            return

        self.stderr.write(
            self.style.ERROR(f'Failed ({backend}): {status["message"]}')
        )
        raise SystemExit(1)
