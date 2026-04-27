from django.contrib import admin
from .models import Violation, ViolationAppeal
from django.utils.html import format_html


@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "reporter",
        "vehicle",
        "category",
        "status",
        "reported_at",
        "viewed",
    )

    list_filter = ("status", "category", "viewed")
    search_fields = ("reporter__username", "vehicle__license_plate")

    ordering = ("-reported_at",)


@admin.register(ViolationAppeal)
class ViolationAppealAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "driver",
        "violation",
        "status",
        "created_at",
        "review_link",
    )

    def review_link(self, obj):
        return format_html(
            '<a class="button" href="/violations/admin/appeals/{}/">Xem</a>',
            obj.id
        )

    review_link.short_description = "Review"