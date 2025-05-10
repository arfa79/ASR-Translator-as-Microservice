from django.core.management.base import BaseCommand
from speech_translator.worker import TranslatorWorker

class Command(BaseCommand):
    help = 'Runs the Translator worker'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Translator worker...'))
        worker = TranslatorWorker()
        worker.run() 