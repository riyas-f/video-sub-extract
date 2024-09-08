from django.db import models
from ecowiser.users.models import User

class Video(models.Model):
    user = models.ForeignKey(User, related_name='videos', on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    video_path = models.CharField(max_length=1000, null=True, blank=True)
    vtt_path = models.CharField(max_length=1000, null=True, blank=True)
    upload_timestamp = models.DateTimeField(auto_now_add=True)
    status = models.BooleanField(default=False)

    def __str__(self):
        return self.title
