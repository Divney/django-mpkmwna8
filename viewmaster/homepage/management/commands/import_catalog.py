from django.core.management.base import BaseCommand

from homepage.catalog import import_catalog_from_videos_txt


class Command(BaseCommand):
    help = 'Import videos.txt into the Video catalog (production / S3 mode).'

    def handle(self, *args, **options):
        count = import_catalog_from_videos_txt()
        self.stdout.write(self.style.SUCCESS(f'Imported {count} videos from videos.txt'))
