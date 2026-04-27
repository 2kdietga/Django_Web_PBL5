import os
from django.core.files.base import ContentFile
from django.utils import timezone


def save_latest_frame(device, uploaded_file):
    """
    Chỉ giữ 1 frame mới nhất cho mỗi device.
    Ghi đè file cũ (không delete để tránh lỗi lock file Windows).
    """

    ext = os.path.splitext(uploaded_file.name)[1].lower() or ".jpg"
    filename = f"device_{device.id}{ext}"

    # ❌ BỎ delete
    # if device.latest_frame:
    #     device.latest_frame.delete(save=False)

    # reset pointer để đảm bảo đọc đúng
    uploaded_file.seek(0)

    # ghi đè file
    device.latest_frame.save(
        filename,
        ContentFile(uploaded_file.read()),
        save=False
    )

    device.latest_frame_at = timezone.now()
    device.save(update_fields=["latest_frame", "latest_frame_at"])