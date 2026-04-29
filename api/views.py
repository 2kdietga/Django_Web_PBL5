from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from categories.models import Category
from devices.models import Device
from devices.services import save_latest_frame
from violations.models import Violation

from .ai_client import AIServiceError, analyze_frame_with_ai_server
from .frame_buffer import add_frame, clear_frames, get_frames
from .timing import StepTimer
from .video_utils import cleanup_exported_video, export_frames_to_mp4_file


class UploadAndDetectAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def _timer_enabled(self):
        """
        Bật/tắt debug timing.

        Trong settings.py có thể thêm:
        API_DEBUG_TIMING = True

        Nếu không khai báo, mặc định chạy theo DEBUG.
        """
        return bool(getattr(settings, "API_DEBUG_TIMING", settings.DEBUG))

    def post(self, request):
        timer = StepTimer("api_upload", enabled=self._timer_enabled())

        def respond(payload, status=200, log=True):
            """
            Response helper: tự gắn _timing_ms vào JSON khi đang debug.
            """
            if timer.enabled:
                payload.update(timer.as_dict())

            if log:
                timer.log()

            return Response(payload, status=status)

        # ===== 1. IMAGE =====
        try:
            image = request.FILES.get("image")
            timer.mark("01_get_image")
        except Exception as e:
            timer.mark("01_get_image_failed")
            return respond(
                {
                    "detail": "Upload interrupted",
                    "error": str(e),
                },
                status=400,
            )

        if not image:
            timer.mark("01_missing_image")
            return respond(
                {
                    "detail": "Missing image",
                },
                status=400,
            )

        # ===== 2. DEVICE TOKEN =====
        token = request.headers.get("X-DEVICE-TOKEN")
        timer.mark("02_get_device_token")

        if not token:
            return respond(
                {
                    "detail": "Missing X-DEVICE-TOKEN",
                },
                status=401,
            )

        # ===== 3. QUERY DEVICE =====
        device = (
            Device.objects.filter(token=token, is_active=True)
            .select_related("vehicle")
            .first()
        )
        timer.mark("03_query_device")

        if not device:
            return respond(
                {
                    "detail": "Invalid device token",
                },
                status=401,
            )

        # ===== 4. SAVE LAST SEEN =====
        try:
            device.last_seen = timezone.now()
            device.save(update_fields=["last_seen"])
            timer.mark("04_save_last_seen")
        except Exception as e:
            timer.mark("04_save_last_seen_failed")
            return respond(
                {
                    "detail": "Failed to update device last_seen",
                    "error": str(e),
                },
                status=500,
            )

        # ===== 5. SAVE LIVE FRAME =====
        try:
            image.seek(0)
            save_latest_frame(device, image)
            image.seek(0)
            timer.mark("05_save_latest_frame")

        except Exception as e:
            timer.mark("05_save_latest_frame_failed")
            return respond(
                {
                    "detail": "Failed to save latest frame",
                    "error": str(e),
                },
                status=500,
            )

        # ===== 6. BUFFER FRAME FOR VIDEO EVIDENCE =====
        try:
            image.seek(0)
            add_frame(device.token, image)
            image.seek(0)
            timer.mark("06_add_frame_buffer")

        except Exception as e:
            image.seek(0)
            timer.mark("06_add_frame_buffer_failed")
            # Không nên làm chết request chỉ vì buffer lỗi
            # nhưng vẫn trả debug để biết có lỗi.
            if getattr(settings, "API_STRICT_BUFFER_ERROR", False):
                return respond(
                    {
                        "detail": "Failed to add frame to buffer",
                        "error": str(e),
                    },
                    status=500,
                )

        # ===== 7. DRIVER =====
        card_uid = (request.data.get("card_uid") or "").strip()
        timer.mark("07_read_card_uid")

        if not card_uid:
            return respond(
                {
                    "detail": "Missing card_uid",
                },
                status=400,
            )

        reporter = Account.objects.filter(card_uid=card_uid).first()
        timer.mark("08_query_driver")

        if not reporter:
            return respond(
                {
                    "detail": "Driver not found",
                },
                status=404,
            )

        # ===== 8. VEHICLE =====
        vehicle = device.vehicle
        timer.mark("09_get_vehicle")

        if vehicle is None:
            return respond(
                {
                    "detail": "Device has no vehicle",
                },
                status=400,
            )

        # ===== 9. AI SERVER =====
        try:
            image.seek(0)
            result = analyze_frame_with_ai_server(
                image_file=image,
                device_key=device.token,
                card_uid=card_uid,
            )
            image.seek(0)
            timer.mark("10_call_ai_server")

        except AIServiceError as e:
            timer.mark("10_call_ai_server_failed")
            return respond(
                {
                    "detail": f"AI server error: {str(e)}",
                },
                status=502,
            )

        except Exception as e:
            timer.mark("10_call_ai_server_unexpected_failed")
            return respond(
                {
                    "detail": f"AI unexpected error: {str(e)}",
                },
                status=500,
            )

        # ===== 10. SAVE LATEST AI RESULT FOR LIVE VIEW =====
        try:
            update_fields = []

            if hasattr(device, "latest_ai_status"):
                device.latest_ai_status = result.get("status", "UNKNOWN")
                update_fields.append("latest_ai_status")

            if hasattr(device, "latest_ai_json"):
                device.latest_ai_json = result
                update_fields.append("latest_ai_json")

            if hasattr(device, "latest_ai_at"):
                device.latest_ai_at = timezone.now()
                update_fields.append("latest_ai_at")

            if update_fields:
                device.save(update_fields=update_fields)

            timer.mark("11_save_latest_ai")

        except Exception as e:
            timer.mark("11_save_latest_ai_failed")
            # Không làm chết request chỉ vì lỗi lưu trạng thái live
            if getattr(settings, "API_STRICT_AI_STATE_ERROR", False):
                return respond(
                    {
                        "detail": "Failed to save latest AI result",
                        "error": str(e),
                    },
                    status=500,
                )

        # ===== 11. READ RESULT =====
        status_eye = result.get("status", "UNKNOWN")
        should_create_eye_violation = result.get("should_create_violation", False)

        eye_closed_streak = result.get("eye_closed_streak", 0)
        ear = result.get("ear")
        baseline_ear = result.get("baseline_ear")
        is_calibrated = result.get("is_calibrated", False)

        head_yaw = result.get("head_yaw", 0.0)
        head_direction = result.get("head_direction", "FORWARD")
        head_turn_score = result.get("head_turn_score", 0)
        head_status = result.get("head_status", "SAFE")

        should_create_head_turn_violation = result.get(
            "should_create_head_turn_violation",
            False,
        )

        should_create_any_violation = (
            should_create_eye_violation or should_create_head_turn_violation
        )
        timer.mark("12_parse_ai_result")

        base_payload = {
            "ok": True,
            "eye_status": status_eye,
            "eye_closed_streak": eye_closed_streak,
            "ear": ear,
            "baseline_ear": baseline_ear,
            "is_calibrated": is_calibrated,
            "head_yaw": head_yaw,
            "head_direction": head_direction,
            "head_turn_score": head_turn_score,
            "head_status": head_status,
            "vehicle": vehicle.license_plate,
            "driver": reporter.username,
        }

        # ===== 12. NO VIOLATION =====
        if not should_create_any_violation:
            timer.mark("13_build_no_violation_response")

            return respond(
                {
                    **base_payload,
                    "violation": False,
                },
                status=200,
            )

        # ===== 13. DECIDE TYPE =====
        if should_create_eye_violation:
            category_name = getattr(settings, "DROWSINESS_CATEGORY_NAME", "Drowsiness")
            violation_title = "Drowsiness"
            violation_description = (
                f"Eye closed too long ({eye_closed_streak} frames) | "
                f"EAR={ear} | baseline_EAR={baseline_ear}"
            )
            cooldown = int(
                getattr(settings, "DROWSINESS_VIOLATION_COOLDOWN_SECONDS", 20)
            )
            violation_kind = "eye"

        else:
            category_name = getattr(settings, "HEAD_TURN_CATEGORY_NAME", "Head Turn")
            violation_title = "Head Turn"
            violation_description = (
                f"Head turned too long ({head_turn_score} score) | "
                f"yaw={head_yaw} | direction={head_direction}"
            )
            cooldown = int(
                getattr(settings, "HEAD_TURN_VIOLATION_COOLDOWN_SECONDS", 20)
            )
            violation_kind = "head"

        timer.mark("14_decide_violation_type")

        # ===== 14. CATEGORY =====
        try:
            category, _ = Category.objects.get_or_create(name=category_name)
            timer.mark("15_get_or_create_category")
        except Exception as e:
            timer.mark("15_get_or_create_category_failed")
            return respond(
                {
                    "detail": "Failed to get or create category",
                    "error": str(e),
                },
                status=500,
            )

        # ===== 15. COOLDOWN =====
        now = timezone.now()
        recent = Violation.objects.filter(
            reporter=reporter,
            vehicle=vehicle,
            category=category,
            reported_at__gte=now - timedelta(seconds=cooldown),
        ).first()
        timer.mark("16_check_cooldown")

        if recent:
            timer.mark("17_build_cooldown_response")

            return respond(
                {
                    **base_payload,
                    "violation": True,
                    "created": False,
                    "cooldown": True,
                    "cooldown_seconds": cooldown,
                    "violation_id": recent.id,
                    "violation_kind": violation_kind,
                },
                status=200,
            )

        # ===== 16. EXPORT VIDEO FROM DJANGO BUFFER =====
        exported_video = None

        try:
            fps = int(getattr(settings, "DROWSINESS_FPS", 5))
            video_frames = get_frames(device.token)
            timer.mark("17_get_video_frames")

            exported_video = export_frames_to_mp4_file(
                frames=video_frames,
                fps=fps,
            )
            timer.mark("18_export_video")

        except Exception as e:
            timer.mark("18_export_video_failed")
            return respond(
                {
                    "detail": "Failed to export violation video",
                    "error": str(e),
                },
                status=500,
            )

        # ===== 17. CREATE VIOLATION =====
        violation = None

        try:
            violation = Violation.objects.create(
                category=category,
                reporter=reporter,
                vehicle=vehicle,
                title=violation_title,
                description=violation_description,
            )
            timer.mark("19_create_violation_db_row")

            # ===== 17.1 SAVE IMAGE =====
            try:
                image.seek(0)

                image_name = image.name or "violation.jpg"
                if "." not in image_name:
                    image_name = f"{image_name}.jpg"

                violation.image.save(
                    image_name,
                    image,
                    save=False,
                )
                timer.mark("20_save_violation_image")

            except Exception as e:
                timer.mark("20_save_violation_image_failed")
                raise RuntimeError(f"Failed to save violation image: {str(e)}")

            # ===== 17.2 SAVE VIDEO =====
            try:
                if exported_video:
                    exported_video.file.seek(0)

                    violation.video.save(
                        exported_video.filename,
                        exported_video.file,
                        save=False,
                    )
                    timer.mark("21_save_violation_video")
                else:
                    timer.mark("21_no_exported_video")

            except Exception as e:
                timer.mark("21_save_violation_video_failed")
                raise RuntimeError(f"Failed to save violation video: {str(e)}")

            # ===== 17.3 FINAL SAVE =====
            violation.save()
            timer.mark("22_final_violation_save")

            clear_frames(device.token)
            timer.mark("23_clear_frame_buffer")

        except Exception as e:
            timer.mark("24_create_violation_failed")
            return respond(
                {
                    "detail": "Failed to create violation",
                    "error": str(e),
                },
                status=500,
            )

        finally:
            cleanup_exported_video(exported_video)
            timer.mark("25_cleanup_exported_video")

        # ===== 18. RESPONSE =====
        timer.mark("26_build_violation_response")

        return respond(
            {
                **base_payload,
                "violation": True,
                "created": True,
                "violation_id": violation.id if violation else None,
                "violation_kind": violation_kind,
                "has_video": bool(exported_video),
                "image_url": violation.image.url if violation and violation.image else None,
                "video_url": violation.video.url if violation and violation.video else None,
            },
            status=201,
        )