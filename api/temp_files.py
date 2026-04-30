# không được truyền trực tiếp request.FILES["image"] vào thread, vì sau khi request kết thúc object file có thể bị đóng.
import os
import uuid

from django.conf import settings


def save_uploaded_file_to_temp(uploaded_file, subdir="tmp/violation_images"):
    temp_dir = os.path.join(settings.MEDIA_ROOT, subdir)
    os.makedirs(temp_dir, exist_ok=True)

    original_name = uploaded_file.name or "violation.jpg"
    _, ext = os.path.splitext(original_name)

    if not ext:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    abs_path = os.path.join(temp_dir, filename)

    uploaded_file.seek(0)

    with open(abs_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    uploaded_file.seek(0)

    return abs_path, filename