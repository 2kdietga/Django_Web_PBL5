from django.contrib import admin
from .models import Device

class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'vehicle', 'is_active', 'last_seen')
    search_fields = ('name', 'token')
admin.site.register(Device, DeviceAdmin)
