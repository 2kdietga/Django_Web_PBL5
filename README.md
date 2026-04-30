# Django_Web - Hệ thống quản lý vi phạm tài xế

`Django_Web` là ứng dụng Django dùng để quản lý người dùng, phương tiện, thiết bị giám sát và các vi phạm được phát hiện từ luồng ảnh gửi lên từ thiết bị. Dự án đóng vai trò web/backend chính trong hệ thống PBL5: thiết bị gửi frame kèm token và UID thẻ RFID, Django xác thực dữ liệu, gọi FastAPI AI để phân tích hành vi, lưu trạng thái live và tạo hồ sơ vi phạm khi cần.

## Chức năng chính

- Đăng ký, đăng nhập, đăng xuất và cập nhật hồ sơ người dùng.
- Quản lý tài khoản tùy biến bằng email, có hỗ trợ `card_uid` để nhận diện tài xế qua RFID.
- Quản lý phương tiện theo biển số, mẫu xe và ngày đăng ký.
- Quản lý thiết bị bằng `token`, liên kết thiết bị với phương tiện, lưu đường dẫn frame live mới nhất trên local disk và kết quả AI mới nhất.
- Nhận frame từ thiết bị qua REST API `/api/upload/`.
- Gọi FastAPI AI server để phân tích:
  - trạng thái mắt, EAR, baseline EAR, số frame nhắm mắt liên tiếp;
  - hướng đầu, yaw, điểm quay đầu và trạng thái quay đầu.
- Tự động tạo vi phạm khi AI báo tài xế buồn ngủ hoặc quay đầu quá lâu.
- Tạo bản ghi vi phạm nhanh và đưa việc lưu ảnh/video bằng chứng sang background threadpool.
- Lưu ảnh vi phạm và video bằng chứng ngắn từ buffer frame sau khi response API đã trả về.
- Người dùng xem danh sách vi phạm của chính mình, lọc theo ngày và loại vi phạm.
- Người dùng xem chi tiết vi phạm và gửi đơn kháng cáo.
- Admin/staff xem danh sách kháng cáo, duyệt hoặc từ chối kháng cáo.
- Trang live view theo thiết bị, tự động refresh frame local và trạng thái AI.
- Live frame không upload lên Cloudinary; chỉ lưu tạm ở local để giảm độ trễ và chi phí lưu trữ.
- Hỗ trợ Cloudinary cho ảnh/video bằng chứng vi phạm, WhiteNoise cho static file và Gunicorn/Docker để deploy.

## Công nghệ sử dụng

- Python 3.13
- Django 6.0.4
- Django REST Framework 3.17.1
- PostgreSQL
- Cloudinary và `django-cloudinary-storage`
- OpenCV, NumPy, ffmpeg cho xử lý frame/video bằng chứng
- httpx để gọi FastAPI AI server
- `ThreadPoolExecutor` để xử lý ảnh/video bằng chứng vi phạm ở background
- WhiteNoise để phục vụ static file
- Gunicorn cho production
- Docker

## Cấu trúc thư mục

```text
Django_Web/
├── Django_Web/          # Cấu hình project: settings, urls, wsgi, asgi
├── accounts/            # Tài khoản, đăng nhập, đăng ký, hồ sơ, ảnh người dùng
├── api/                 # API nhận frame, gọi AI server, buffer frame, background jobs, xuất video
├── categories/          # Danh mục/loại vi phạm
├── devices/             # Thiết bị giám sát, live frame, live view
├── vehicles/            # Phương tiện
├── violations/          # Vi phạm và kháng cáo
├── templates/           # Giao diện HTML
├── static/              # CSS/JS nguồn
├── staticfiles/         # Static sau collectstatic
├── media/               # Media local, gồm live_frames/ cho frame live
├── manage.py
├── requirements.txt
├── Dockerfile
└── README.md
```

## Các app trong dự án

### `accounts`

Quản lý người dùng bằng model tùy biến `Account`.

Các trường chính:

- `first_name`, `last_name`, `username`, `email`, `phone_number`
- `card_uid`: UID thẻ RFID dùng để map tài xế khi thiết bị gửi dữ liệu
- `is_admin`, `is_staff`, `is_active`, `is_superadmin`

Ngoài ra có `UserImage` để lưu ảnh người dùng và chọn ảnh đại diện.

Các route chính:

- `/accounts/register/`: đăng ký
- `/accounts/login/`: đăng nhập
- `/accounts/logout/`: đăng xuất
- `/accounts/profile/`: xem/cập nhật hồ sơ

### `vehicles`

Quản lý phương tiện.

Model `Vehicle` gồm:

- `license_plate`: biển số, duy nhất
- `model`: mẫu xe
- `registration_date`: ngày đăng ký

### `devices`

Quản lý thiết bị gửi frame về server.

Model `Device` gồm:

- `name`: tên thiết bị
- `token`: token xác thực thiết bị, duy nhất
- `vehicle`: phương tiện đang gắn thiết bị
- `is_active`: trạng thái hoạt động
- `last_seen`: thời điểm thiết bị gửi dữ liệu gần nhất
- `latest_frame_path`, `latest_frame_at`: đường dẫn frame live mới nhất trên local disk
- `latest_ai_status`, `latest_ai_json`, `latest_ai_at`: kết quả AI mới nhất

Các route chính:

- `/devices/<id>/live/`: trang live view theo thiết bị
- `/devices/<id>/frame/`: trả frame mới nhất của thiết bị

### `categories`

Quản lý loại vi phạm.

Model `Category` gồm:

- `name`
- `description`
- `severality_level`
- `is_active`
- `created_at`

### `violations`

Quản lý vi phạm và kháng cáo.

Model `Violation` gồm:

- `category`: loại vi phạm
- `reporter`: tài xế/người dùng liên quan
- `vehicle`: phương tiện vi phạm
- `title`, `description`
- `reported_at`
- `image`: ảnh bằng chứng
- `video`: video bằng chứng
- `viewed`
- `status`: `pending`, `confirmed`, `dismissed`, `appealed`

Model `ViolationAppeal` gồm:

- `violation`: vi phạm được kháng cáo
- `driver`: tài xế gửi kháng cáo
- `reason`: lý do
- `status`: `pending`, `approved`, `rejected`
- `admin_note`
- `created_at`, `reviewed_at`

Các route chính:

- `/violations/list/`: danh sách vi phạm của user đang đăng nhập
- `/violations/detail/<violation_id>/`: chi tiết vi phạm
- `/violations/<violation_id>/appeal/`: gửi kháng cáo
- `/violations/admin/appeals/`: danh sách kháng cáo cho staff
- `/violations/admin/appeals/<appeal_id>/`: chi tiết kháng cáo
- `/violations/admin/appeals/<appeal_id>/review/`: duyệt hoặc từ chối kháng cáo

### `api`

Cung cấp API để thiết bị gửi ảnh lên và nhận kết quả xử lý.

Endpoint chính:

```http
POST /api/upload/
```

Header bắt buộc:

```http
X-DEVICE-TOKEN: <device_token>
```

Body dạng `multipart/form-data`:

```text
image=<file ảnh>
card_uid=<UID thẻ RFID của tài xế>
```

Luồng xử lý:

1. Kiểm tra file `image`.
2. Kiểm tra `X-DEVICE-TOKEN`.
3. Tìm `Device` đang active theo token.
4. Cập nhật `last_seen`.
5. Lưu frame mới nhất vào `MEDIA_ROOT/live_frames/device_<id>/` để phục vụ live view, không upload Cloudinary.
6. Đưa frame vào buffer để có thể xuất video bằng chứng.
7. Tìm tài xế theo `card_uid`.
8. Kiểm tra thiết bị đã liên kết với phương tiện.
9. Gửi ảnh sang FastAPI AI server tại `${AI_SERVER_URL}/v1/analyze/`.
10. Lưu kết quả AI mới nhất vào `Device`.
11. Nếu không có vi phạm, trả JSON trạng thái.
12. Nếu có vi phạm, xác định loại vi phạm và kiểm tra cooldown.
13. Snapshot frame buffer, lưu ảnh hiện tại vào file tạm và tạo nhanh bản ghi `Violation`.
14. Đưa job xử lý bằng chứng vào background threadpool.
15. Trả response `202 Accepted` ngay với `queued=true`; ảnh/video sẽ được gắn vào `Violation` sau khi worker chạy xong.

Ví dụ request bằng `curl`:

```bash
curl -X POST http://127.0.0.1:8000/api/upload/ \
  -H "X-DEVICE-TOKEN: DEVICE_TOKEN" \
  -F "card_uid=CARD_UID" \
  -F "image=@frame.jpg"
```

Ví dụ response khi không có vi phạm:

```json
{
  "ok": true,
  "eye_status": "EYE_OPEN",
  "eye_closed_streak": 0,
  "ear": 0.31,
  "baseline_ear": 0.3,
  "is_calibrated": true,
  "head_yaw": 0.0,
  "head_direction": "FORWARD",
  "head_turn_score": 0,
  "head_status": "SAFE",
  "violation": false,
  "vehicle": "43A-12345",
  "driver": "driver01"
}
```

Ví dụ response khi tạo vi phạm và đã đưa job bằng chứng vào hàng đợi:

```json
{
  "ok": true,
  "violation": true,
  "created": true,
  "queued": true,
  "evidence_ready": false,
  "violation_id": 1,
  "violation_kind": "eye",
  "has_video": false,
  "image_url": null,
  "video_url": null
}
```

Response này dùng HTTP status `202`. Trang chi tiết vi phạm sẽ có ảnh/video sau khi background worker lưu xong bằng chứng.

## Luồng nghiệp vụ tổng quát

```text
Thiết bị camera/RFID
    ↓ POST /api/upload/
Django_Web
    ↓ xác thực token thiết bị
    ↓ tìm tài xế theo card_uid
    ↓ lưu latest frame local + buffer frame
FastAPI AI Server
    ↓ trả kết quả phân tích mắt/đầu
Django_Web
    ↓ lưu latest_ai_json
    ↓ tạo Violation nếu vượt ngưỡng
    ↓ enqueue job xử lý ảnh/video bằng chứng
Background ThreadPool
    ↓ lưu ảnh bằng chứng
    ↓ xuất video MP4 từ buffer frame
    ↓ gắn image/video vào Violation
Người dùng/Admin
    ↓ xem vi phạm, kháng cáo, duyệt kháng cáo
```

## Background threadpool xử lý bằng chứng

Dự án dùng `api.background_jobs` để tách phần xử lý nặng ra khỏi request `/api/upload/`.

Khi AI báo có vi phạm và không bị cooldown, Django chỉ tạo bản ghi `Violation` trước, sau đó enqueue job bằng `ThreadPoolExecutor`. Job background sẽ:

1. Mở lại bản ghi `Violation` theo `violation_id`.
2. Lưu ảnh bằng chứng từ file tạm trong `MEDIA_ROOT/tmp/violation_images/`.
3. Xuất video MP4 từ snapshot frame buffer bằng OpenCV, nếu có `ffmpeg` thì convert sang H.264/yuv420p để trình duyệt dễ phát.
4. Lưu `image` và `video` qua Django storage hiện tại, tức là Cloudinary nếu đã cấu hình.
5. Xóa buffer frame của thiết bị sau khi bằng chứng đã lưu xong.
6. Dọn file ảnh tạm và thư mục video tạm.
7. Gọi `close_old_connections()` để tránh giữ connection database cũ trong thread.

Các điểm cần lưu ý:

- Không truyền trực tiếp `request.FILES` hoặc object request vào thread vì sau khi request kết thúc file có thể bị đóng.
- View chỉ truyền `violation_id`, `device_token`, đường dẫn ảnh tạm và list frame đã snapshot.
- Nếu worker lỗi, request tạo vi phạm vẫn đã trả về thành công; lỗi được ghi log qua logger của `api.background_jobs`.
- Vì threadpool chạy trong memory của process Django/Gunicorn, job có thể mất nếu process bị restart trước khi xử lý xong. Với production cần độ bền cao hơn, có thể thay bằng Celery/RQ và message broker.
- Với nhiều Gunicorn worker, mỗi process có threadpool và frame buffer riêng; thiết bị nên gửi liên tục vào cùng instance nếu cần video buffer ổn định.

## Cài đặt môi trường local

### 1. Tạo và kích hoạt virtual environment

```bash
python -m venv .venv
```

Trên Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Trên macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Cài dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Tạo file `.env`

Tạo file `.env` ở thư mục gốc dự án. Không commit file này lên Git.

```env
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB_NAME

AI_SERVER_URL=http://127.0.0.1:8001
AI_SERVICE_TOKEN=your-ai-service-token
AI_TIMEOUT_SECONDS=10

CLOUDINARY_CLOUD_NAME=your-cloud-name
CLOUDINARY_API_KEY=your-api-key
CLOUDINARY_API_SECRET=your-api-secret
```

Số thread background xử lý bằng chứng hiện được cấu hình trong `Django_Web/settings.py`:

```python
VIOLATION_WORKER_THREADS = 1
```

Tăng giá trị này nếu server cần xử lý nhiều vi phạm đồng thời. Cần cân nhắc CPU/RAM vì mỗi job có thể giữ nhiều frame OpenCV và chạy export video.

Nếu không dùng `DATABASE_URL`, có thể cấu hình các biến database riêng theo code trong `settings.py`:

```env
DB_NAME=pbl5_db
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
```

### 4. Chạy migrate

```bash
python manage.py migrate
```

### 5. Tạo superuser

Vì project dùng custom user model với các required fields `username`, `first_name`, `last_name`, khi tạo superuser cần nhập đầy đủ các trường Django yêu cầu.

```bash
python manage.py createsuperuser
```

### 6. Thu thập static file

```bash
python manage.py collectstatic --noinput
```

### 7. Chạy server

```bash
python manage.py runserver
```

Mở trình duyệt tại:

```text
http://127.0.0.1:8000/
```

## Cấu hình dữ liệu ban đầu

Sau khi đăng nhập admin tại `/admin/`, cần tạo các dữ liệu sau để API hoạt động:

1. Tạo `Account` cho tài xế và gán `card_uid`.
2. Tạo `Vehicle` với biển số xe.
3. Tạo `Device`:
   - nhập `token` dùng cho header `X-DEVICE-TOKEN`;
   - bật `is_active`;
   - liên kết với `Vehicle`.
4. Tạo hoặc để hệ thống tự tạo `Category` khi phát hiện vi phạm:
   - mặc định buồn ngủ dùng tên `Drowsiness`;
   - mặc định quay đầu dùng tên `Head Turn`.

## Biến cấu hình quan trọng

| Biến | Ý nghĩa |
| --- | --- |
| `SECRET_KEY` | Secret key của Django |
| `DEBUG` | Bật/tắt debug mode |
| `ALLOWED_HOSTS` | Danh sách host được phép truy cập |
| `DATABASE_URL` | Chuỗi kết nối PostgreSQL, ưu tiên hơn `DB_*` |
| `DB_NAME` | Tên database nếu không dùng `DATABASE_URL` |
| `DB_USER` | User database |
| `DB_PASSWORD` | Password database |
| `DB_HOST` | Host database |
| `DB_PORT` | Port database |
| `AI_SERVER_URL` | URL FastAPI AI server |
| `AI_SERVICE_TOKEN` | Token gửi sang AI server qua `X-AI-SERVICE-TOKEN` |
| `AI_TIMEOUT_SECONDS` | Timeout khi gọi AI server |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary cloud name |
| `CLOUDINARY_API_KEY` | Cloudinary API key |
| `CLOUDINARY_API_SECRET` | Cloudinary API secret |

Một số setting AI/cooldown có giá trị fallback trong code nếu chưa khai báo:

| Setting | Mặc định | Ý nghĩa |
| --- | ---: | --- |
| `DROWSINESS_CATEGORY_NAME` | `Drowsiness` | Tên category cho vi phạm buồn ngủ |
| `HEAD_TURN_CATEGORY_NAME` | `Head Turn` | Tên category cho vi phạm quay đầu |
| `DROWSINESS_VIOLATION_COOLDOWN_SECONDS` | `20` | Thời gian chặn tạo trùng vi phạm buồn ngủ |
| `HEAD_TURN_VIOLATION_COOLDOWN_SECONDS` | `20` | Thời gian chặn tạo trùng vi phạm quay đầu |
| `DROWSINESS_FPS` | `5` | FPS khi xuất video bằng chứng |
| `DROWSINESS_BUFFER_SECONDS` | `5` | Số giây frame giữ trong buffer |
| `DROWSINESS_EYE_CLOSED_FRAMES` | `6` | Ngưỡng hiển thị frame nhắm mắt trong live view |
| `DROWSINESS_HEAD_TURN_VIOLATION_FRAMES` | `15` | Ngưỡng hiển thị quay đầu trong live view |
| `VIOLATION_WORKER_THREADS` | `1` | Số thread background xử lý ảnh/video bằng chứng vi phạm |
| `API_DEBUG_TIMING` | `False` | Bật log `_timing_ms` cho từng bước trong API upload |

## API AI server cần tương thích

Django gọi AI server bằng:

```http
POST ${AI_SERVER_URL}/v1/analyze/
X-AI-SERVICE-TOKEN: <AI_SERVICE_TOKEN>
```

Body `multipart/form-data`:

```text
image=<file ảnh>
device_key=<device.token>
card_uid=<UID thẻ RFID>
```

Response AI server nên trả các field mà Django đang đọc:

```json
{
  "status": "EYE_OPEN",
  "should_create_violation": false,
  "eye_closed_streak": 0,
  "ear": 0.31,
  "baseline_ear": 0.3,
  "is_calibrated": true,
  "head_yaw": 0.0,
  "head_direction": "FORWARD",
  "head_turn_score": 0,
  "head_status": "SAFE",
  "should_create_head_turn_violation": false
}
```

## Giao diện người dùng

- `/`: trang đăng nhập.
- `/violations/list/`: danh sách vi phạm của user hiện tại.
- `/violations/detail/<id>/`: chi tiết vi phạm, ảnh/video bằng chứng và trạng thái kháng cáo.
- `/accounts/profile/`: hồ sơ cá nhân.
- `/devices/<id>/live/`: màn hình live theo thiết bị, refresh mỗi 500ms.
- `/admin/`: Django Admin.

## Admin và phân quyền

- User thường chỉ xem được vi phạm của chính họ vì query trong `violation_list` và `violation_detail` lọc theo `reporter=request.user`.
- Các trang duyệt kháng cáo dùng `@staff_member_required`, chỉ staff/admin truy cập được.
- Admin có thể quản lý tài khoản, ảnh user, danh mục, xe, thiết bị, vi phạm và kháng cáo trong Django Admin.

## Media và static file

- Static file:
  - nguồn nằm trong `static/`;
  - sau `collectstatic` được đưa vào `staticfiles/`;
  - WhiteNoise được dùng trong middleware để phục vụ static file production.
- Media bằng chứng:
  - default storage đang dùng `MediaCloudinaryStorage`;
  - ảnh/video vi phạm được background worker lưu lên Cloudinary nếu cấu hình Cloudinary đầy đủ;
  - ngay sau khi API trả `202`, bản ghi vi phạm có thể chưa có ảnh/video cho đến khi worker hoàn tất;
  - các file này dùng cho trang chi tiết vi phạm và kháng cáo.
- Live frame:
  - không dùng `MediaCloudinaryStorage` và không upload Cloudinary;
  - mỗi frame mới được ghi trực tiếp vào `MEDIA_ROOT/live_frames/device_<id>/`;
  - `Device.latest_frame_path` lưu relative path của frame mới nhất;
  - service `save_latest_frame()` giữ tối đa `LIVE_FRAME_KEEP = 5` file gần nhất cho mỗi thiết bị và tự xóa frame cũ;
  - route `/devices/<id>/frame/` trả frame mới nhất để màn hình live refresh liên tục.

## Chạy bằng Docker

Build image:

```bash
docker build -t django-web-pbl5 .
```

Chạy container:

```bash
docker run --env-file .env -p 10000:10000 django-web-pbl5
```

Dockerfile sẽ:

1. dùng image `python:3.13-slim`;
2. cài thư viện hệ thống cần cho PostgreSQL, OpenCV và ffmpeg;
3. cài dependencies trong `requirements.txt`;
4. chạy `collectstatic`;
5. khi container start sẽ chạy `migrate` rồi khởi động Gunicorn tại port `${PORT:-10000}`.

## Deploy

Dự án đã chuẩn bị cho môi trường production như Render hoặc dịch vụ tương tự:

- Sử dụng `gunicorn Django_Web.wsgi:application`.
- Port mặc định trong Docker là `10000`.
- Database ưu tiên đọc từ `DATABASE_URL`.
- Static file được phục vụ qua WhiteNoise.
- Ảnh/video vi phạm được xử lý bằng background threadpool và có thể lưu trên Cloudinary; live frame vẫn lưu local trong `MEDIA_ROOT/live_frames/`.
- Nếu chạy nhiều Gunicorn worker, mỗi worker có threadpool và memory buffer riêng. Cấu hình worker/process cần phù hợp với luồng frame thực tế.

Các biến môi trường production tối thiểu:

```env
SECRET_KEY=...
DEBUG=False
ALLOWED_HOSTS=your-domain.com
DATABASE_URL=...
AI_SERVER_URL=...
AI_SERVICE_TOKEN=...
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

Nếu deployment chỉ cần live view mà chưa cần lưu ảnh/video bằng chứng lên Cloudinary, live frame vẫn hoạt động bằng local storage. Khi cần lưu bằng chứng vi phạm trên Cloudinary thì phải cấu hình đủ ba biến `CLOUDINARY_*`.

## Ghi chú bảo mật

- Không commit `.env`, token thiết bị, token AI service, thông tin database hoặc Cloudinary secret.
- `Device.token` là thông tin xác thực thiết bị, cần tạo đủ dài và khó đoán.
- `AI_SERVICE_TOKEN` phải khớp giữa Django và FastAPI AI server.
- Khi deploy production, đặt `DEBUG=False` và cấu hình `ALLOWED_HOSTS` đúng domain.
- Nên thay các giá trị mặc định trong `settings.py` bằng biến môi trường an toàn trước khi public repo.

## Lệnh thường dùng

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

Kiểm tra cấu hình Django:

```bash
python manage.py check
```

## Troubleshooting

### API trả `Missing image`

Request chưa gửi file với field name là `image`.

### API trả `Missing X-DEVICE-TOKEN`

Request thiếu header:

```http
X-DEVICE-TOKEN: <device_token>
```

### API trả `Invalid device token`

Không tìm thấy `Device` active tương ứng với token. Kiểm tra trong Django Admin:

- `token` có đúng không;
- `is_active` có bật không.

### API trả `Driver not found`

Không tìm thấy `Account` có `card_uid` trùng với `card_uid` thiết bị gửi lên.

### API trả `Device has no vehicle`

Thiết bị chưa được liên kết với `Vehicle`.

### API trả `AI server error`

Django gọi FastAPI AI server thất bại. Kiểm tra:

- `AI_SERVER_URL`;
- `AI_SERVICE_TOKEN`;
- endpoint `/v1/analyze/` của FastAPI;
- network giữa Django và AI server;
- timeout `AI_TIMEOUT_SECONDS`.

### Không xem được frame live

Kiểm tra:

- thiết bị đã gửi frame thành công chưa;
- `Device.latest_frame_path` có dữ liệu không;
- file tương ứng có tồn tại trong `MEDIA_ROOT/live_frames/device_<id>/` không;
- tiến trình Django/container có quyền ghi vào thư mục `media/live_frames/` không;
- route `/devices/<id>/frame/` có trả ảnh không.

## Trạng thái hiện tại của README

Tài liệu này được viết dựa trên mã nguồn hiện tại trong project `Django_Web`, bao gồm models, views, URLs, settings, Dockerfile và luồng API đang triển khai.
