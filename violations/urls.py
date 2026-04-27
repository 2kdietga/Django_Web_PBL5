from . import views
from django.urls import path

urlpatterns = [
    path('list/', views.violation_list, name='violation_list'),
    path('detail/<int:violation_id>/', views.violation_detail, name='violation_detail'),
    path("<int:violation_id>/appeal/", views.create_appeal, name="create_appeal"),

    path("admin/appeals/", views.appeal_review_list, name="appeal_review_list"),
    path("admin/appeals/<int:appeal_id>/", views.appeal_review_detail, name="appeal_review_detail"),
    path("admin/appeals/<int:appeal_id>/review/", views.appeal_review_action, name="appeal_review_action"),
]
