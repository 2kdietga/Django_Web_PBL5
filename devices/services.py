import os
import uuid

from django.conf import settings
from django.utils import timezone


LIVE_FRAME_KEEP = 5


def _safe_ext(filename):
    ext = os.path.splitext(filename or "")[1].lower()

    if ext in [".jpg", ".jpeg", ".png", ".webp"]:
        return ext

    return ".jpg"


def _cleanup_old_live_frames(live_dir, current_filename, keep=LIVE_FRAME_KEEP):
    try:
        files = []

        for name in os.listdir(live_dir):
            if name == current_filename:
                continue

            path = os.path.join(live_dir, name)

            if name.endswith(".tmp"):
                try:
                    os.remove(path)
                except OSError:
                    pass
                continue

            if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue

            if os.path.isfile(path):
                files.append((path, os.path.getmtime(path)))

        files.sort(key=lambda x: x[1], reverse=True)

        # Giữ lại keep - 1 file cũ, cộng với file hiện tại
        for path, _mtime in files[max(keep - 1, 0):]:
            try:
                os.remove(path)
            except OSError:
                pass

    except OSError:
        pass


def save_latest_frame(device, uploaded_file):
    """
    Lưu live frame vào local disk, không upload Cloudinary.

    Field dùng:
    - device.latest_frame_path
    - device.latest_frame_at
    """

    ext = _safe_ext(getattr(uploaded_file, "name", ""))
    live_dir = os.path.join(settings.MEDIA_ROOT, "live_frames", f"device_{device.id}")
    os.makedirs(live_dir, exist_ok=True)

    final_filename = (
        f"{timezone.now().strftime('%Y%m%d_%H%M%S_%f')}_"
        f"{uuid.uuid4().hex}{ext}"
    )
    temp_filename = f"{final_filename}.tmp"

    final_abs_path = os.path.join(live_dir, final_filename)
    temp_abs_path = os.path.join(live_dir, temp_filename)

    uploaded_file.seek(0)

    with open(temp_abs_path, "wb") as f:
        for chunk in uploaded_file.chunks():
            f.write(chunk)

    os.replace(temp_abs_path, final_abs_path)

    rel_path = os.path.join(
        "live_frames",
        f"device_{device.id}",
        final_filename,
    ).replace("\\", "/")

    device.latest_frame_path = rel_path
    device.latest_frame_at = timezone.now()
    device.save(update_fields=["latest_frame_path", "latest_frame_at"])

    uploaded_file.seek(0)

    _cleanup_old_live_frames(live_dir, final_filename)

    return final_abs_path