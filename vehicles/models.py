from django.db import models

class Vehicle(models.Model):
    license_plate = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=100)
    registration_date = models.DateField()

    def __str__(self):
        return self.license_plate
