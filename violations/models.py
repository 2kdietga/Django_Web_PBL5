from django.db import models

from cloudinary_storage.storage import (
    MediaCloudinaryStorage,
    VideoMediaCloudinaryStorage,
)

from categories.models import Category
from accounts.models import Account
from vehicles.models import Vehicle


class Violation(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("dismissed", "Dismissed"),
        ("appealed", "Appealed"),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    reporter = models.ForeignKey(Account, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.CASCADE)

    title = models.CharField(max_length=200, default="Violation Report")
    description = models.TextField()
    reported_at = models.DateTimeField(auto_now_add=True)

    image = models.ImageField(
        upload_to="violations/",
        storage=MediaCloudinaryStorage(),
        null=True,
        blank=True,
    )

    video = models.FileField(
        upload_to="violations/videos/",
        storage=VideoMediaCloudinaryStorage(),
        null=True,
        blank=True,
    )

    viewed = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    class Meta:
        verbose_name = "Violation"
        verbose_name_plural = "Violations"
        ordering = ["-reported_at"]

    def __str__(self):
        reporter_name = self.reporter.get_full_name() or self.reporter.username
        return f"{reporter_name} - {self.category.name}"


class ViolationAppeal(models.Model):
    violation = models.OneToOneField(
        Violation,
        on_delete=models.CASCADE,
        related_name="appeal",
    )

    driver = models.ForeignKey(Account, on_delete=models.CASCADE)

    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="pending",
    )

    admin_note = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True, auto_now=True)

    def __str__(self):
        return f"Appeal #{self.id} - Violation #{self.violation.id}"