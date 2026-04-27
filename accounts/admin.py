from django.contrib import admin
from .models import Account, UserImage
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

# 1. Tạo bộ lọc tùy chỉnh bên thanh SideBar
class ImageCountFilter(admin.SimpleListFilter):
    title = 'Trạng thái ảnh' # Tiêu đề hiển thị
    parameter_name = 'has_images' # Biến trên URL

    def lookups(self, request, model_admin):
        return (
            ('no', 'Chưa có ảnh'),
            ('yes', 'Đã có ảnh'),
        )

    def queryset(self, request, queryset):
        # Đếm số lượng ảnh của mỗi Account
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
    # Thêm 'image_count_display' vào list_display
    list_display = ('email', 'first_name', 'last_name', 'image_count_display', 'is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    search_fields = ('email', 'username', 'first_name', 'last_name', 'card_uid')

    # Thêm bộ lọc vừa tạo vào list_filter
    list_filter = (ImageCountFilter, 'is_active', 'is_staff')
    
    filter_horizontal = ()
    fieldsets = ()
    ordering = ('-date_joined',)
    inlines = [UserImageInline]

    # 2. Hàm hiển thị số lượng ảnh và cảnh báo màu sắc
    @admin.display(description='Số lượng ảnh')
    def image_count_display(self, obj):
        count = obj.images.count()
        if count == 0:
            # Trả về text màu đỏ nếu chưa có ảnh
            from django.utils.html import format_html
            return format_html('<b style="color: red;">Chưa có ảnh</b>')
        return f"{count} ảnh"

admin.site.register(Account, AccountAdmin)