"""Authentication views for user accounts."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from accounts.forms import UserRegistrationForm


def login_view(request):
    """Handle user login with DaisyUI-styled form."""
    if request.user.is_authenticated:
        return redirect("space_list")

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Bem-vindo, {user.username}!")
            return redirect("space_list")
        messages.error(request, "Usuário ou senha inválidos.")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/login.html", {"form": form})


def register_view(request):
    """Handle user registration with DaisyUI-styled form."""
    if request.user.is_authenticated:
        return redirect("space_list")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Conta criada com sucesso!")
            return redirect("space_list")
        messages.error(request, "Corrija os erros abaixo.")
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    """Log out the current user and redirect to login."""
    logout(request)
    messages.info(request, "Você saiu da sua conta.")
    return redirect("accounts:login")
