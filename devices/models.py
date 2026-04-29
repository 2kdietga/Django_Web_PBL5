from django.db import models
from vehicles.models import Vehicle


class Device(models.Model):
    name = models.CharField(max_length=100)

    token = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
    )

    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True, db_index=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Live frame local, không dùng Cloudinary
    latest_frame_path = models.CharField(max_length=500, blank=True, null=True)
    latest_frame_at = models.DateTimeField(null=True, blank=True)

    latest_ai_status = models.CharField(max_length=100, blank=True, default="")
    latest_ai_json = models.JSONField(default=dict, blank=True)
    latest_ai_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name