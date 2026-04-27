import os
import uuid
import shutil
import subprocess

import cv2
from django.conf import settings


def export_frames_to_mp4(
    frames,
    fps=5,
    subdir="violations/videos",
    target_width=640,
):
    """
    Xuất list frame OpenCV BGR thành MP4.
    Trả về relative path để lưu vào FileField/ImageField của Django.
    Ví dụ: violations/videos/abc123.mp4
    """

    if not frames:
        return None

    media_root = settings.MEDIA_ROOT
    output_dir = os.path.join(media_root, subdir)
    os.makedirs(output_dir, exist_ok=True)

    raw_filename = f"{uuid.uuid4().hex}_raw.mp4"
    final_filename = f"{uuid.uuid4().hex}.mp4"

    raw_abs_path = os.path.join(output_dir, raw_filename)
    final_abs_path = os.path.join(output_dir, final_filename)

    final_rel_path = os.path.join(subdir, final_filename).replace("\\", "/")
    raw_rel_path = os.path.join(subdir, raw_filename).replace("\\", "/")

    first = frames[0]
    h, w = first.shape[:2]

    if w > target_width:
        new_w = target_width
        new_h = int(h * target_width / w)
    else:
        new_w = w
        new_h = h

    # Một số codec cần width/height chẵn
    if new_w % 2 != 0:
        new_w -= 1
    if new_h % 2 != 0:
        new_h -= 1

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(raw_abs_path, fourcc, fps, (new_w, new_h))

    if not writer.isOpened():
        raise RuntimeError("Cannot open cv2.VideoWriter")

    try:
        for frame in frames:
            if frame is None:
                continue

            resized = cv2.resize(frame, (new_w, new_h))
            writer.write(resized)

    finally:
        writer.release()

    # Nếu có ffmpeg thì convert sang H.264 + yuv420p để trình duyệt dễ phát
    ffmpeg_path = shutil.which("ffmpeg")

    if ffmpeg_path:
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            raw_abs_path,
            "-vcodec",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            final_abs_path,
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        if result.returncode == 0 and os.path.exists(final_abs_path):
            try:
                os.remove(raw_abs_path)
            except OSError:
                pass

            return final_rel_path

    # Nếu không có ffmpeg thì fallback về file OpenCV tạo
    return raw_rel_path