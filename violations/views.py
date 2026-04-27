from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.admin.views.decorators import staff_member_required

from .models import Violation, ViolationAppeal
from categories.models import Category

@login_required
def violation_list(request):
    # Chỉ lấy vi phạm của user đang đăng nhập
    qs = Violation.objects.filter(reporter=request.user).select_related(
        "category", "vehicle", "reporter"
    ).order_by("-reported_at")

    # Lấy dữ liệu filter từ querystring
    from_date_str = request.GET.get("from_date", "").strip()
    to_date_str = request.GET.get("to_date", "").strip()
    selected_category = request.GET.get("category", "").strip()

    # Filter theo ngày (reported_at là DateTimeField)
    from_date = parse_date(from_date_str) if from_date_str else None
    to_date = parse_date(to_date_str) if to_date_str else None

    if from_date:
        qs = qs.filter(reported_at__date__gte=from_date)
    if to_date:
        qs = qs.filter(reported_at__date__lte=to_date)

    # Filter theo category
    if selected_category:
        qs = qs.filter(category_id=selected_category)

    context = {
        "violations": qs,
        "links": Category.objects.all().order_by("name"),  # danh sách category cho dropdown
        "from_date": from_date_str,
        "to_date": to_date_str,
        "selected_category": selected_category,
    }
    return render(request, "violation_list.html", context)

@login_required
def violation_detail(request, violation_id):
    violation = get_object_or_404(
        Violation.objects.select_related("category", "vehicle", "reporter"),
        id=violation_id,
        reporter=request.user
    )

    if not violation.viewed:
        violation.viewed = True
        violation.save(update_fields=["viewed"])

    appeal = getattr(violation, "appeal", None)

    context = {
        "violation": violation,
        "appeal": appeal,
    }
    return render(request, "violation_detail.html", context)

@login_required
@require_POST
def create_appeal(request, violation_id):
    violation = get_object_or_404(
        Violation,
        id=violation_id,
        reporter=request.user
    )

    # ❌ đã kháng cáo rồi thì chặn
    if hasattr(violation, "appeal"):
        return JsonResponse({
            "ok": False,
            "error": "Bạn đã kháng cáo rồi"
        }, status=400)

    reason = request.POST.get("reason", "").strip()

    if not reason:
        return JsonResponse({
            "ok": False,
            "error": "Vui lòng nhập lý do"
        }, status=400)

    # tạo appeal
    appeal = ViolationAppeal.objects.create(
        violation=violation,
        driver=request.user,
        reason=reason
    )

    # update trạng thái violation
    violation.status = "appealed"
    violation.save(update_fields=["status"])
    return redirect("violation_detail", violation_id=violation.id)





@staff_member_required
def appeal_review_list(request):
    appeals = ViolationAppeal.objects.select_related(
        "violation",
        "driver",
        "violation__category",
        "violation__vehicle",
        "violation__reporter",
    ).order_by("-created_at")

    context = {
        "appeals": appeals,
    }
    return render(request, "admin_appeal_list.html", context)


@staff_member_required
def appeal_review_detail(request, appeal_id):
    appeal = get_object_or_404(
        ViolationAppeal.objects.select_related(
            "violation",
            "driver",
            "violation__category",
            "violation__vehicle",
            "violation__reporter",
        ),
        id=appeal_id,
    )

    context = {
        "appeal": appeal,
        "violation": appeal.violation,
    }
    return render(request, "admin_appeal_detail.html", context)


@staff_member_required  
@require_POST
def appeal_review_action(request, appeal_id):
    appeal = get_object_or_404(
        ViolationAppeal.objects.select_related("violation"),
        id=appeal_id,
    )

    action = request.POST.get("action")
    admin_note = request.POST.get("admin_note", "").strip()

    if appeal.status != "pending":
        messages.warning(request, "Đơn kháng cáo này đã được xử lý rồi.")
        return redirect("appeal_review_detail", appeal_id=appeal.id)

    appeal.admin_note = admin_note
    appeal.reviewed_at = timezone.now()

    violation = appeal.violation

    if action == "approve":
        appeal.status = "approved"
        violation.status = "dismissed"
        messages.success(request, "Đã chấp nhận kháng cáo.")
    elif action == "reject":
        appeal.status = "rejected"
        violation.status = "confirmed"
        messages.success(request, "Đã từ chối kháng cáo.")
    else:
        messages.error(request, "Hành động không hợp lệ.")
        return redirect("appeal_review_detail", appeal_id=appeal.id)

    appeal.save(update_fields=["status", "admin_note", "reviewed_at"])
    violation.save(update_fields=["status"])

    return redirect("appeal_review_detail", appeal_id=appeal.id)