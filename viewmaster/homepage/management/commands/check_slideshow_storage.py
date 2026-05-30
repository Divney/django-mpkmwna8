from django.core.management.base import BaseCommand

from homepage.slideshow_sources import storage_check_status


class Command(BaseCommand):
    help = 'Verify slideshow video storage (local directory or S3).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Minimal output; stop S3 scan after 10 missing keys.',
        )
        parser.add_argument(
            '--progress-every',
            type=int,
            default=100,
            metavar='N',
            help='In verbose mode, log progress every N videos (default: 100).',
        )

    def handle(self, *args, **options):
        verbose = not options['quiet']

        def write(message):
            self.stdout.write(message)

        if verbose:
            self.stdout.write('ViewMaster storage check')
            self.stdout.write('-' * 40)

        status = storage_check_status(
            verbose=verbose,
            write=write,
            progress_interval=options['progress_every'],
        )
        backend = status['backend']

        if verbose:
            self.stdout.write('-' * 40)
            self.stdout.write(
                f'Summary: {status.get("checked", 0)} checked, '
                f'{len(status.get("missing", []))} missing'
            )
            missing_listed = status.get('missing_listed') or status.get('missing', [])
            if missing_listed:
                self.stdout.write('Missing keys:')
                for key in missing_listed:
                    self.stdout.write(f'  {key}')
                extra = len(status.get('missing', [])) - len(missing_listed)
                if extra > 0:
                    self.stdout.write(f'  ... and {extra} more')

        if status['ok']:
            self.stdout.write(
                self.style.SUCCESS(f'OK ({backend}): {status["message"]}')
            )
            sample_url = status.get('sample_url')
            if sample_url:
                self.stdout.write(f'Sample URL: {sample_url}')
            return

        self.stderr.write(
            self.style.ERROR(f'Failed ({backend}): {status["message"]}')
        )
        raise SystemExit(1)
