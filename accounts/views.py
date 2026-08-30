"""Authentication views for user accounts."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from accounts.forms import ProfileForm, UserRegistrationForm
from accounts.models import Profile


def _redirect_for_user(user):
    """Return the redirect target based on the user's role.

    Desde a Fase 6 o usuário comum cai no Início, e não mais direto no passo 1
    da reserva: a tela de Início responde "tenho algo agora?", que é a pergunta
    mais frequente de quem entra. Quem quer reservar tem o botão em destaque.
    """
    if user.is_staff:
        return redirect("admin_dashboard:admin_dashboard")
    return redirect("inicio")


def login_view(request):
    """Handle login, redirecting automatically based on the user's role."""
    if request.user.is_authenticated:
        return _redirect_for_user(request.user)

    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Bem-vindo, {user.username}!")
            return _redirect_for_user(user)
        messages.error(request, "Usuário ou senha inválidos.")
    else:
        form = AuthenticationForm(request)

    return render(request, "accounts/login.html", {"form": form})


def register_view(request):
    """Handle user registration with DaisyUI-styled form."""
    if request.user.is_authenticated:
        return _redirect_for_user(request.user)

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Conta criada com sucesso!")
            return redirect("inicio")
        messages.error(request, "Corrija os erros abaixo.")
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def logout_view(request):
    """Log out the current user and redirect to login."""
    logout(request)
    messages.info(request, "Você saiu da sua conta.")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    """Let the user fill in the data the reservation flow reads from them.

    Sem esta tela o modelo ``Profile`` seria um campo que ninguém preenche, e o
    resumo da reserva mostraria uma lotação eternamente vazia. O passo 3 não
    pergunta lotação — pergunta aqui, uma vez.
    """
    perfil = Profile.carregar(request.user)

    if request.method == "POST":
        form = ProfileForm(request.POST, instance=perfil)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil atualizado.")
            return redirect("accounts:profile")
        messages.error(request, "Corrija os erros abaixo.")
    else:
        form = ProfileForm(instance=perfil)

    return render(request, "accounts/profile.html", {"form": form, "perfil": perfil})
