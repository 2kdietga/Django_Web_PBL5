import os
import uuid
import shutil
import tempfile
import subprocess
from dataclasses import dataclass

import cv2
from django.core.files import File


@dataclass
class ExportedVideo:
    file: File
    filename: str
    temp_dir: str


def cleanup_exported_video(exported_video):
    """
    Đóng file và xóa thư mục tạm sau khi đã upload lên Django storage.
    """
    if not exported_video:
        return

    try:
        exported_video.file.close()
    except Exception:
        pass

    try:
        shutil.rmtree(exported_video.temp_dir, ignore_errors=True)
    except Exception:
        pass


def export_frames_to_mp4_file(frames, fps=5, target_width=640):
    """
    Xuất list frame OpenCV BGR thành file MP4 tạm.

    Không lưu trực tiếp vào MEDIA_ROOT.
    View sẽ dùng:
        violation.video.save(exported.filename, exported.file, save=False)

    Dùng được với:
    - FileSystemStorage local
    - Cloudinary video storage
    - Docker/Render
    """

    if not frames:
        return None

    temp_dir = tempfile.mkdtemp(prefix="violation_video_")

    raw_abs_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}_raw.mp4")
    final_abs_path = os.path.join(temp_dir, f"{uuid.uuid4().hex}.mp4")

    try:
        first = frames[0]
        h, w = first.shape[:2]

        if w > target_width:
            new_w = target_width
            new_h = int(h * target_width / w)
        else:
            new_w = w
            new_h = h

        # Codec/video browser thường cần width/height chẵn
        if new_w % 2 != 0:
            new_w -= 1

        if new_h % 2 != 0:
            new_h -= 1

        if new_w <= 0 or new_h <= 0:
            raise RuntimeError("Invalid video size")

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

        if not os.path.exists(raw_abs_path) or os.path.getsize(raw_abs_path) == 0:
            raise RuntimeError("OpenCV created empty video file")

        output_path = raw_abs_path

        # Nếu có ffmpeg thì convert sang H.264 + yuv420p để browser dễ phát
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
                if os.path.getsize(final_abs_path) > 0:
                    output_path = final_abs_path

        filename = f"{uuid.uuid4().hex}.mp4"
        file_obj = open(output_path, "rb")

        return ExportedVideo(
            file=File(file_obj, name=filename),
            filename=filename,
            temp_dir=temp_dir,
        )

    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise