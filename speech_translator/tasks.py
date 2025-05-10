from celery import shared_task
from .models import Translation
from .services import translate_text

@shared_task(name='translate_text')
def translate_text_task(translation_id):
    try:
        translation = Translation.objects.get(id=translation_id)
        result = translate_text(translation)
        return result
    except Translation.DoesNotExist:
        return {'error': 'Translation not found'}
    except Exception as e:
        return {'error': str(e)} 