import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from .models import Device


def _local_media_path_from_relative_path(relative_path):
    """
    Chuyển Device.latest_frame_path thành absolute path trong MEDIA_ROOT.

    latest_frame_path nên là dạng:
    live_frames/device_1/xxx.jpg

    Không dùng storage Cloudinary cho live frame.
    """
    if not relative_path:
        return None

    safe_relative_path = str(relative_path).replace("\\", "/").lstrip("/")

    media_root = os.path.abspath(settings.MEDIA_ROOT)
    abs_path = os.path.abspath(os.path.join(media_root, safe_relative_path))

    # Chống path traversal: ../../...
    try:
        common_path = os.path.commonpath([media_root, abs_path])
    except ValueError:
        return None

    if common_path != media_root:
        return None

    return abs_path


@never_cache
def device_latest_frame(request, id):
    """
    Trả frame mới nhất của device từ local MEDIA_ROOT.

    Field đúng hiện tại:
    - device.latest_frame_path
    - device.latest_frame_at
    """
    device = get_object_or_404(Device, id=id)

    latest_frame_path = getattr(device, "latest_frame_path", None)

    if not latest_frame_path:
        raise Http404("No frame available")

    frame_path = _local_media_path_from_relative_path(latest_frame_path)

    if not frame_path:
        raise Http404("Invalid frame path")

    if not os.path.exists(frame_path):
        raise Http404("Frame file not found")

    if not os.path.isfile(frame_path):
        raise Http404("Frame path is not a file")

    content_type, _encoding = mimetypes.guess_type(frame_path)
    content_type = content_type or "image/jpeg"

    response = FileResponse(
        open(frame_path, "rb"),
        content_type=content_type,
    )

    # Tránh browser cache ảnh cũ
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"

    return response


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

        if getattr(device, "latest_frame_path", None):
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