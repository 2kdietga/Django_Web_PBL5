import os

from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.conf import settings
from django.utils import timezone

from .models import Device


def device_latest_frame(request, id):
    """
    Trả frame mới nhất của device.

    Hỗ trợ cả:
    - local FileSystemStorage: dùng FileResponse từ .path
    - Cloudinary/storage ngoài: redirect tới .url
    """
    device = get_object_or_404(Device, id=id)

    if not device.latest_frame:
        raise Http404("No frame available")

    # Nếu storage có URL thì dùng được cho cả local và Cloudinary
    try:
        frame_url = device.latest_frame.url
    except Exception:
        frame_url = None

    # Nếu có path local thì serve trực tiếp
    try:
        frame_path = device.latest_frame.path

        if frame_path and os.path.exists(frame_path):
            response = FileResponse(
                open(frame_path, "rb"),
                content_type="image/jpeg",
            )

            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

            return response

    except Exception:
        pass

    # Nếu không có path local, ví dụ Cloudinary, redirect sang URL file
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
            try:
                # Dùng route của Django để local/Cloudinary đều chạy
                latest_frame_url = (
                    f"/devices/{device.id}/frame/"
                    f"?t={int(timezone.now().timestamp() * 1000)}"
                )
            except Exception:
                latest_frame_url = None

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