from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import ProfileForm, RegisterForm

def login_view(request):
    if request.user.is_authenticated:
        return redirect("violation_list")  # đổi theo url name của bạn

    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")

        # Vì USERNAME_FIELD = 'email'
        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Sai email hoặc mật khẩu.")
            return render(request, "login.html")

        if not user.is_active:
            messages.error(request, "Tài khoản chưa được kích hoạt.")
            return render(request, "login.html")

        login(request, user)
        return redirect("violation_list")

    return render(request, "login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

def register_view(request):
    if request.user.is_authenticated:
        return redirect("violation_list")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, "Tạo tài khoản thành công.")
            login(request, user)  # đăng nhập luôn
            return redirect("violation_list")
        messages.error(request, "Vui lòng kiểm tra lại thông tin.")
    else:
        form = RegisterForm()

    return render(request, "register.html", {"form": form})

@login_required
def profile_view(request):
    user = request.user
    edit = request.GET.get("edit") == "1"

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Cập nhật thông tin thành công.")
            return redirect("profile")
        messages.error(request, "Vui lòng kiểm tra lại thông tin.")
        edit = True  # nếu lỗi thì giữ chế độ edit
    else:
        form = ProfileForm(instance=user)

    return render(request, "profile.html", {"form": form, "edit": edit})
