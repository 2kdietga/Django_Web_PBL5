import logging
import os
from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.files import File
from django.db import close_old_connections

from .frame_buffer import clear_frames
from .video_utils import cleanup_exported_video, export_frames_to_mp4_file

logger = logging.getLogger(__name__)


VIOLATION_WORKER_THREADS = int(
    getattr(settings, "VIOLATION_WORKER_THREADS", 1)
)

_violation_executor = ThreadPoolExecutor(
    max_workers=VIOLATION_WORKER_THREADS,
    thread_name_prefix="violation-worker",
)


def enqueue_violation_evidence_job(
    *,
    violation_id,
    device_token,
    evidence_image_path,
    evidence_image_name,
    video_frames,
    fps,
):
    """
    Đẩy job xử lý bằng chứng vi phạm sang background thread.

    Không truyền request.FILES hoặc object Django request vào thread.
    Chỉ truyền:
    - violation_id
    - device_token
    - đường dẫn ảnh tạm
    - danh sách frame đã snapshot
    """
    return _violation_executor.submit(
        process_violation_evidence_job,
        violation_id=violation_id,
        device_token=device_token,
        evidence_image_path=evidence_image_path,
        evidence_image_name=evidence_image_name,
        video_frames=video_frames,
        fps=fps,
    )


def process_violation_evidence_job(
    *,
    violation_id,
    device_token,
    evidence_image_path,
    evidence_image_name,
    video_frames,
    fps,
):
    exported_video = None

    close_old_connections()

    try:
        from violations.models import Violation

        violation = Violation.objects.get(id=violation_id)

        # ===== 1. SAVE IMAGE EVIDENCE =====
        if evidence_image_path and os.path.exists(evidence_image_path):
            with open(evidence_image_path, "rb") as f:
                violation.image.save(
                    evidence_image_name or "violation.jpg",
                    File(f),
                    save=False,
                )

        # ===== 2. EXPORT VIDEO EVIDENCE =====
        if video_frames:
            exported_video = export_frames_to_mp4_file(
                frames=video_frames,
                fps=fps,
            )

            if exported_video:
                exported_video.file.seek(0)

                violation.video.save(
                    exported_video.filename,
                    exported_video.file,
                    save=False,
                )

        # ===== 3. FINAL SAVE =====
        violation.save()

        # Sau khi bằng chứng đã tạo xong thì clear buffer
        clear_frames(device_token)

        logger.info(
            "Violation evidence job done | violation_id=%s | has_video=%s",
            violation_id,
            bool(exported_video),
        )

    except Exception:
        logger.exception(
            "Violation evidence job failed | violation_id=%s",
            violation_id,
        )

    finally:
        cleanup_exported_video(exported_video)

        if evidence_image_path and os.path.exists(evidence_image_path):
            try:
                os.remove(evidence_image_path)
            except Exception:
                logger.exception(
                    "Failed to remove temp evidence image: %s",
                    evidence_image_path,
                )

        close_old_connections()