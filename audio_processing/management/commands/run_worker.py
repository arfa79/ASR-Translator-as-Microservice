from django.core.management.base import BaseCommand
from audio_processing.worker import ASRWorker

class Command(BaseCommand):
    help = 'Runs the ASR worker'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting ASR worker...'))
        worker = ASRWorker()
        worker.run() 