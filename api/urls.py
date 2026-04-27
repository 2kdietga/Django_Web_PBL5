from . import views
from django.urls import path

urlpatterns = [
    path("upload/", views.UploadAndDetectAPIView.as_view(), name="upload_and_detect"),
]