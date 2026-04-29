import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Device


def _local_media_path_from_field(file_field):
    """
    Lấy path local từ file_field.name.

    Không dùng file_field.path trước, vì nếu default storage là Cloudinary
    thì .path có thể lỗi hoặc không tồn tại.
    """
    if not file_field:
        return None

    name = getattr(file_field, "name", None)
    if not name:
        return None

    # Chống path traversal
    safe_name = name.replace("\\", "/").lstrip("/")
    abs_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, safe_name))
    media_root = os.path.abspath(settings.MEDIA_ROOT)

    if not abs_path.startswith(media_root):
        return None

    return abs_path


def device_latest_frame(request, id):
    """
    Trả frame mới nhất của device.

    Ưu tiên:
    1. Local file trong MEDIA_ROOT/live_frames/...
    2. Fallback sang storage URL nếu là file cũ trên Cloudinary
    """
    device = get_object_or_404(Device, id=id)

    if not device.latest_frame:
        raise Http404("No frame available")

    # Ưu tiên đọc local bằng latest_frame.name
    frame_path = _local_media_path_from_field(device.latest_frame)

    if frame_path and os.path.exists(frame_path):
        content_type, _encoding = mimetypes.guess_type(frame_path)
        content_type = content_type or "image/jpeg"

        response = FileResponse(
            open(frame_path, "rb"),
            content_type=content_type,
        )

        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
        response["Expires"] = "0"

        return response

    # Fallback cho dữ liệu cũ nếu trước đó latest_frame đã nằm trên Cloudinary
    try:
        frame_url = device.latest_frame.url
    except Exception:
        frame_url = None

    if frame_url:
        return redirect(frame_url)

    raise Http404("Frame file not found")


def device_live_view(request, id):
    device = get_object_or_404(Device, id=id)

    # AJAX: trả JSON trạng thái realtime
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        ai = device.latest_ai_json or {}

        head_turn_threshold = int(
            getattr(settings, "DROWSINESS_HEAD_TURN_VIOLATION_FRAMES", 15)
        )

        eye_closed_streak = ai.get("eye_closed_streak", 0)
        eye_status = ai.get("status", "UNKNOWN")

        ear = ai.get("ear")
        baseline_ear = ai.get("baseline_ear")
        is_calibrated = ai.get("is_calibrated", False)

        head_turn_score = ai.get("head_turn_score", 0)
        head_direction = ai.get("head_direction", "FORWARD")
        head_yaw = ai.get("head_yaw", 0.0)
        head_status = ai.get("head_status")

        if not head_status:
            if head_turn_score == 0:
                head_status = "SAFE"
            elif head_turn_score < head_turn_threshold:
                head_status = "TURNING"
            else:
                head_status = "VIOLATION"

        should_create_violation = ai.get("should_create_violation", False)
        should_create_head_turn_violation = ai.get(
            "should_create_head_turn_violation",
            False,
        )

        latest_frame_url = None

        if device.latest_frame:
            latest_frame_url = (
                f"/devices/{device.id}/frame/"
                f"?t={int(timezone.now().timestamp() * 1000)}"
            )

        return JsonResponse(
            {
                "ok": True,

                # frame
                "latest_frame_url": latest_frame_url,
                "latest_frame_at": (
                    device.latest_frame_at.isoformat()
                    if getattr(device, "latest_frame_at", None)
                    else None
                ),

                # AI chung
                "ai_status": eye_status,
                "latest_ai_at": (
                    device.latest_ai_at.isoformat()
                    if getattr(device, "latest_ai_at", None)
                    else None
                ),
                "is_calibrated": is_calibrated,

                # eye
                "eye_closed_streak": eye_closed_streak,
                "ear": ear,
                "baseline_ear": baseline_ear,

                # head
                "head_direction": head_direction,
                "head_turn_score": head_turn_score,
                "head_yaw": head_yaw,
                "head_status": head_status,

                # violation flags
                "should_create_violation": should_create_violation,
                "should_create_head_turn_violation": should_create_head_turn_violation,
            }
        )

    # Render HTML
    return render(
        request,
        "live_view.html",
        {
            "device": device,
            "DROWSINESS_EYE_CLOSED_FRAMES": getattr(
                settings,
                "DROWSINESS_EYE_CLOSED_FRAMES",
                6,
            ),
            "DROWSINESS_HEAD_TURN_VIOLATION_FRAMES": getattr(
                settings,
                "DROWSINESS_HEAD_TURN_VIOLATION_FRAMES",
                15,
            ),
        },
    )