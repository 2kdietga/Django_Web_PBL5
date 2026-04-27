from django.contrib import admin
from .models import Account, UserImage
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.utils.html import format_html


# 1. Tạo bộ lọc tùy chỉnh bên thanh sidebar
class ImageCountFilter(admin.SimpleListFilter):
    title = 'Trạng thái ảnh'
    parameter_name = 'has_images'

    def lookups(self, request, model_admin):
        return (
            ('no', 'Chưa có ảnh'),
            ('yes', 'Đã có ảnh'),
        )

    def queryset(self, request, queryset):
        queryset = queryset.annotate(img_count=Count('images'))

        if self.value() == 'no':
            return queryset.filter(img_count=0)

        if self.value() == 'yes':
            return queryset.filter(img_count__gt=0)

        return queryset


class UserImageInline(admin.TabularInline):
    model = UserImage
    extra = 1
    max_num = 10


class AccountAdmin(UserAdmin):
    list_display = (
        'email',
        'first_name',
        'last_name',
        'image_count_display',
        'is_active',
    )

    list_display_links = (
        'email',
        'first_name',
        'last_name',
    )

    readonly_fields = (
        'last_login',
        'date_joined',
    )

    search_fields = (
        'email',
        'username',
        'first_name',
        'last_name',
        'card_uid',
    )

    list_filter = (
        ImageCountFilter,
        'is_active',
        'is_staff',
    )

    filter_horizontal = ()
    fieldsets = ()
    ordering = ('-date_joined',)
    inlines = [UserImageInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(img_count=Count('images'))

    @admin.display(description='Số lượng ảnh')
    def image_count_display(self, obj):
        count = getattr(obj, 'img_count', obj.images.count())

        if count == 0:
            return format_html(
                '<b style="color: {};">{}</b>',
                'red',
                'Chưa có ảnh'
            )

        return f"{count} ảnh"


admin.site.register(Account, AccountAdmin)