from celery import shared_task
from .models import AudioFile
from .services import process_audio_file

@shared_task(name='process_audio_file')
def process_audio_file_task(audio_file_id):
    try:
        audio_file = AudioFile.objects.get(id=audio_file_id)
        result = process_audio_file(audio_file)
        return result
    except AudioFile.DoesNotExist:
        return {'error': 'Audio file not found'}
    except Exception as e:
        return {'error': str(e)} 