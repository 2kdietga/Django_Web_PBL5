import httpx
from django.conf import settings


class AIServiceError(Exception):
    pass


def analyze_frame_with_ai_server(image_file, device_key, card_uid=""):
    """
    Gửi ảnh từ Django sang FastAPI AI server.
    FastAPI chỉ trả JSON kết quả AI, không trả frame/video.
    """

    url = f"{settings.AI_SERVER_URL.rstrip('/')}/v1/analyze/"

    image_file.seek(0)

    files = {
        "image": (
            getattr(image_file, "name", "frame.jpg"),
            image_file,
            getattr(image_file, "content_type", "image/jpeg") or "image/jpeg",
        )
    }

    data = {
        "device_key": str(device_key),
        "card_uid": card_uid or "",
    }

    headers = {
        "X-AI-SERVICE-TOKEN": settings.AI_SERVICE_TOKEN,
    }

    try:
        with httpx.Client(timeout=settings.AI_TIMEOUT_SECONDS) as client:
            response = client.post(
                url,
                headers=headers,
                data=data,
                files=files,
            )

        response.raise_for_status()
        return response.json()

    except httpx.TimeoutException:
        raise AIServiceError("AI server timeout")

    except httpx.HTTPStatusError as e:
        raise AIServiceError(
            f"AI server returned {e.response.status_code}: {e.response.text}"
        )

    except httpx.RequestError as e:
        raise AIServiceError(f"Cannot connect to AI server: {str(e)}")

    finally:
        image_file.seek(0)