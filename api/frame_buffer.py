from collections import defaultdict, deque
from threading import Lock

import cv2
import numpy as np
from django.conf import settings


_BUFFER_LOCK = Lock()
_FRAME_BUFFERS = {}


def get_buffer_size():
    fps = int(getattr(settings, "DROWSINESS_FPS", 5))
    seconds = int(getattr(settings, "DROWSINESS_BUFFER_SECONDS", 5))
    return max(1, fps * seconds)


def image_file_to_cv2(image_file):
    image_file.seek(0)
    arr = np.frombuffer(image_file.read(), np.uint8)
    image_file.seek(0)

    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return frame


def add_frame(device_key, image_file):
    frame = image_file_to_cv2(image_file)

    if frame is None:
        return

    device_key = str(device_key)

    with _BUFFER_LOCK:
        if device_key not in _FRAME_BUFFERS:
            _FRAME_BUFFERS[device_key] = deque(maxlen=get_buffer_size())

        _FRAME_BUFFERS[device_key].append(frame)


def get_frames(device_key):
    device_key = str(device_key)

    with _BUFFER_LOCK:
        if device_key not in _FRAME_BUFFERS:
            return []

        return list(_FRAME_BUFFERS[device_key])


def clear_frames(device_key):
    device_key = str(device_key)

    with _BUFFER_LOCK:
        if device_key in _FRAME_BUFFERS:
            _FRAME_BUFFERS[device_key].clear()