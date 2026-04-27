# import os

# from django.http import FileResponse, Http404, JsonResponse
# from django.shortcuts import get_object_or_404, render
# from django.conf import settings

# from ai.drowsiness.state import STATE_STORE
# from .models import Device


# def device_latest_frame(request, id):
#     device = get_object_or_404(Device, id=id)

#     if not device.latest_frame:
#         raise Http404("No frame available")

#     frame_path = device.latest_frame.path
#     if not os.path.exists(frame_path):
#         raise Http404("Frame file not found")

#     return FileResponse(open(frame_path, "rb"), content_type="image/jpeg")


# def device_live_view(request, id):
#     device = get_object_or_404(Device, id=id)

#     # AJAX: trả JSON trạng thái realtime
#     if request.headers.get("x-requested-with") == "XMLHttpRequest":
#         state = STATE_STORE.get(device.token)

#         head_turn_threshold = int(
#             getattr(settings, "DROWSINESS_HEAD_TURN_VIOLATION_FRAMES", 15)
#         )

#         if not state:
#             return JsonResponse({
#                 "eye_closed_streak": 0,
#                 "head_direction": "FORWARD",
#                 "head_turn_score": 0,
#                 "head_yaw": 0.0,
#                 "head_status": "SAFE",
#             })

#         head_turn_score = getattr(state, "head_turn_score", 0)
#         head_direction = getattr(state, "head_direction", "FORWARD")
#         head_yaw = getattr(state, "last_yaw", 0.0)

#         if head_turn_score == 0:
#             head_status = "SAFE"
#         elif head_turn_score < head_turn_threshold:
#             head_status = "TURNING"
#         else:
#             head_status = "VIOLATION"

#         return JsonResponse({
#             "eye_closed_streak": getattr(state, "eye_closed_streak", 0),
#             "head_direction": head_direction,
#             "head_turn_score": head_turn_score,
#             "head_yaw": head_yaw,
#             "head_status": head_status,
#         })

#     # Render HTML
#     return render(
#         request,
#         "live_view.html",
#         {
#             "device": device,
#             "DROWSINESS_EYE_CLOSED_FRAMES": getattr(
#                 settings, "DROWSINESS_EYE_CLOSED_FRAMES", 6
#             ),
#         },
#     )