
def login_view(request):
    if request.user.is_authenticated:
        return redirect("revenue:dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get("next") or "revenue:dashboard")
        messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    return render(request, "revenue/login.html")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("revenue:dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        # Sécurité : après la création du compte, on ne connecte pas
        # automatiquement l'utilisateur. Il doit passer par la page login.
        form.save()
        messages.success(request, "Compte créé avec succès. Veuillez vous connecter pour accéder à l'application.")
        return redirect("revenue:login")
    return render(request, "revenue/register.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("revenue:login")


def _can_manage(user):
    if not user.is_authenticated:
        return False
    from django.contrib.auth.models import Group
    role_groups = Group.objects.filter(name__in=["Admin", "Manager"])
    if not role_groups.exists():
        return True
    return user.is_staff or user.groups.filter(name__in=["Admin", "Manager"]).exists()

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RegisterForm, UploadExcelForm
from .models import DataUpload
from .services.importer import process_upload
from .services.pptx_export import generate_pptx


@login_required
def dashboard(request):
    form = UploadExcelForm()
    latest_upload = DataUpload.objects.filter(status="processed").first()
    context = {
        "form": form,
        "latest_upload": latest_upload,
        "uploads": DataUpload.objects.all()[:10],
    }
    return render(request, "revenue/dashboard.html", context)


@login_required
def upload_excel(request):
    if not _can_manage(request.user):
        messages.error(request, "Vous n’avez pas le rôle nécessaire pour importer des fichiers.")
        return redirect("revenue:dashboard")
    if request.method != "POST":
        return redirect("revenue:dashboard")
    form = UploadExcelForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, form.errors.as_text())
        return redirect("revenue:dashboard")

    upload = form.save(commit=False)
    upload.original_filename = request.FILES["file"].name
    upload.save()
    upload = process_upload(upload)
    if upload.status == "processed":
        messages.success(request, f"Import réussi : {upload.rows_imported} lignes importées, {upload.rows_rejected} rejetées.")
    else:
        messages.error(request, "Échec import : " + " | ".join(upload.errors))
    return redirect("revenue:dashboard")


@login_required
def delete_upload(request):
    if not _can_manage(request.user):
        messages.error(request, "Vous n’avez pas le rôle nécessaire pour supprimer des fichiers.")
        return redirect("revenue:dashboard")
    if request.method != "POST":
        return redirect("revenue:dashboard")

    upload_id = request.POST.get("upload_id")
    if not upload_id:
        messages.error(request, "Veuillez sélectionner un fichier à supprimer.")
        return redirect("revenue:dashboard")

    upload = get_object_or_404(DataUpload, id=upload_id)
    filename = upload.original_filename

    # Supprime aussi le fichier physique stocké dans MEDIA_ROOT.
    if upload.file:
        upload.file.delete(save=False)

    # Les RevenueRecord liés sont supprimés automatiquement grâce au CASCADE.
    upload.delete()
    messages.success(request, f"Fichier supprimé : {filename}")
    return redirect("revenue:dashboard")


@login_required
def export_powerpoint(request):
    filters = {
        k: v for k, v in request.GET.items()
        if k in {"upload_id", "date_from", "date_to", "category", "package", "sections", "week_id", "month_id", "granularity"} and v
    }
    upload = None
    upload_id = filters.get("upload_id")
    if upload_id:
        upload = DataUpload.objects.filter(id=upload_id).first()
    report = generate_pptx(filters=filters, upload=upload, generated_by_task=False)
    if not report.file:
        raise Http404("Rapport introuvable")
    return FileResponse(report.file.open("rb"), as_attachment=True, filename="chinguitel_revenue_report.pptx")
