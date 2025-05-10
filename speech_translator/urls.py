from django.urls import path
from . import views
 
urlpatterns = [
    path('', views.translate_text, name='translate_text'),
    path('job/<str:job_id>/', views.translation_status, name='translation_status'),
] 