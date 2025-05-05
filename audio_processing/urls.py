from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_audio, name='upload_audio'),
    path('job/<str:job_id>/', views.audio_job_status, name='audio_job_status'),
]