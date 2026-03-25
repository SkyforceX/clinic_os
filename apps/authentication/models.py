from django.db import models
from django.utils import timezone

class OtpRequest(models.Model):
    phone = models.CharField(max_length=20)
    otp = models.CharField(max_length=8)
    time_sent = models.DateTimeField(default=timezone.now)
    used = models.BooleanField(default=False)

    def is_valid(self):
        from datetime import timedelta
        return (not self.used) and (timezone.now() - self.time_sent < timedelta(minutes=3))
