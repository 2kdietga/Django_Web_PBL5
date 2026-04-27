from datetime import timedelta

from django.utils import timezone
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response

from accounts.models import Account
from categories.models import Category
from devices.services import save_latest_frame
from violations.models import Violation
from devices.models import Device

from .ai_client import analyze_frame_with_ai_server, AIServiceError
from .frame_buffer import add_frame, get_frames, clear_frames
from .video_utils import export_frames_to_mp4_file, cleanup_exported_video


class UploadAndDetectAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        # ===== 1. IMAGE =====
        try:
            image = request.FILES.get("image")
        except Exception as e:
            return Response(
                {
                    "detail": "Upload interrupted",
                    "error": str(e),
                },
                status=400,
            )

        if not image:
            return Response({"detail": "Missing image"}, status=400)

        # ===== 2. DEVICE =====
        token = request.headers.get("X-DEVICE-TOKEN")
        if not token:
            return Response({"detail": "Missing X-DEVICE-TOKEN"}, status=401)

        device = (
            Device.objects.filter(token=token, is_active=True)
            .select_related("vehicle")
            .first()
        )

        if not device:
            return Response({"detail": "Invalid device token"}, status=401)

        device.last_seen = timezone.now()
        device.save(update_fields=["last_seen"])

        # ===== 3. SAVE LIVE FRAME =====
        try:
            image.seek(0)
            save_latest_frame(device, image)
            image.seek(0)

        except Exception as e:
            return Response(
                {
                    "detail": "Failed to save latest frame",
                    "error": str(e),
                },
                status=500,
            )

        # ===== 3.1 BUFFER FRAME FOR VIDEO EVIDENCE =====
        try:
            image.seek(0)
            add_frame(device.token, image)
            image.seek(0)

        except Exception:
            image.seek(0)

        # ===== 4. DRIVER =====
        card_uid = (request.data.get("card_uid") or "").strip()
        if not card_uid:
            return Response({"detail": "Missing card_uid"}, status=400)

        reporter = Account.objects.filter(card_uid=card_uid).first()
        if not reporter:
            return Response({"detail": "Driver not found"}, status=404)

        # ===== 5. VEHICLE =====
        vehicle = device.vehicle
        if vehicle is None:
            return Response({"detail": "Device has no vehicle"}, status=400)

        # ===== 6. AI SERVER =====
        try:
            image.seek(0)
            result = analyze_frame_with_ai_server(
                image_file=image,
                device_key=device.token,
                card_uid=card_uid,
            )
            image.seek(0)

        except AIServiceError as e:
            return Response(
                {
                    "detail": f"AI server error: {str(e)}",
                },
                status=502,
            )

        except Exception as e:
            return Response(
                {
                    "detail": f"AI unexpected error: {str(e)}",
                },
                status=500,
            )

        # ===== 6.1 SAVE LATEST AI RESULT FOR LIVE VIEW =====
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

        except Exception:
            # Không làm chết request chỉ vì lỗi lưu trạng thái live
            pass

        # ===== 7. READ RESULT =====
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

        # ===== 8. NO VIOLATION =====
        if not should_create_any_violation:
            return Response(
                {
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
                    "violation": False,
                    "vehicle": vehicle.license_plate,
                    "driver": reporter.username,
                },
                status=200,
            )

        # ===== 9. DECIDE TYPE =====
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

        category, _ = Category.objects.get_or_create(name=category_name)

        # ===== 10. COOLDOWN =====
        now = timezone.now()
        recent = Violation.objects.filter(
            reporter=reporter,
            vehicle=vehicle,
            category=category,
            reported_at__gte=now - timedelta(seconds=cooldown),
        ).first()

        if recent:
            return Response(
                {
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
                    "violation": True,
                    "created": False,
                    "cooldown": True,
                    "cooldown_seconds": cooldown,
                    "violation_id": recent.id,
                    "violation_kind": violation_kind,
                },
                status=200,
            )

        # ===== 11. EXPORT VIDEO FROM DJANGO BUFFER =====
        exported_video = None

        try:
            fps = int(getattr(settings, "DROWSINESS_FPS", 5))
            video_frames = get_frames(device.token)

            exported_video = export_frames_to_mp4_file(
                frames=video_frames,
                fps=fps,
            )

        except Exception as e:
            return Response(
                {
                    "detail": "Failed to export violation video",
                    "error": str(e),
                },
                status=500,
            )

        # ===== 12. CREATE VIOLATION =====
        violation = None

        try:
            violation = Violation.objects.create(
                category=category,
                reporter=reporter,
                vehicle=vehicle,
                title=violation_title,
                description=violation_description,
            )

            # Save image
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

            except Exception as e:
                raise RuntimeError(f"Failed to save violation image: {str(e)}")

            # Save video
            try:
                if exported_video:
                    exported_video.file.seek(0)

                    violation.video.save(
                        exported_video.filename,
                        exported_video.file,
                        save=False,
                    )

            except Exception as e:
                raise RuntimeError(f"Failed to save violation video: {str(e)}")

            violation.save()

            clear_frames(device.token)

        except Exception as e:
            return Response(
                {
                    "detail": "Failed to create violation",
                    "error": str(e),
                },
                status=500,
            )

        finally:
            cleanup_exported_video(exported_video)

        return Response(
            {
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