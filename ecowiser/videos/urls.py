from django.urls import path
from .views import upload_video, process_video, video_search, history

app_name = 'videos' 

urlpatterns = [
    path('upload/', upload_video, name='upload_video'),
    path('process/', process_video, name='process_video'),
    path('search/', video_search, name='video_search'),
    path('history/', history, name='video_history'),
]
