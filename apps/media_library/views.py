from __future__ import annotations

import json
import mimetypes
import os

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from apps.media_library.models import MediaFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_image_dimensions(file_obj) -> tuple[int | None, int | None]:
    """Trả về (width, height) nếu là ảnh, không thì (None, None)."""
    try:
        from PIL import Image
        file_obj.seek(0)
        img = Image.open(file_obj)
        return img.width, img.height
    except Exception:
        return None, None


def _save_media_file(uploaded_file, request) -> MediaFile:
    original_name = uploaded_file.name
    file_type     = MediaFile.detect_file_type(original_name)
    mime          = mimetypes.guess_type(original_name)[0] or "application/octet-stream"

    media = MediaFile(
        name      = original_name,
        file_type = file_type,
        mime_type = mime,
        file_size = uploaded_file.size,
        created_by = request.user if request.user.is_authenticated else None,
    )
    media.file.save(original_name, uploaded_file, save=False)

    # Lấy kích thước ảnh nếu là image
    if file_type == MediaFile.TYPE_IMAGE:
        w, h = _detect_image_dimensions(uploaded_file)
        media.width  = w
        media.height = h

    media.save()
    return media


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
def index(request):
    """Trang chính — gallery tất cả file."""
    type_filter = request.GET.get("type", "")
    search      = request.GET.get("q", "").strip()
    page_num    = request.GET.get("page", 1)

    qs = MediaFile.objects.select_related("created_by").all()

    if type_filter in {MediaFile.TYPE_IMAGE, MediaFile.TYPE_PDF,
                       MediaFile.TYPE_DOCX, MediaFile.TYPE_EXCEL, MediaFile.TYPE_OTHER}:
        qs = qs.filter(file_type=type_filter)

    if search:
        qs = qs.filter(name__icontains=search)

    paginator = Paginator(qs, 40)
    page      = paginator.get_page(page_num)

    # Thống kê nhanh — đảm bảo tất cả key luôn có giá trị (tránh VariableDoesNotExist)
    from django.db.models import Count
    raw_counts = {
        r["file_type"]: r["cnt"]
        for r in MediaFile.objects.values("file_type").annotate(cnt=Count("id"))
    }
    type_counts = {
        MediaFile.TYPE_IMAGE: raw_counts.get(MediaFile.TYPE_IMAGE, 0),
        MediaFile.TYPE_PDF:   raw_counts.get(MediaFile.TYPE_PDF,   0),
        MediaFile.TYPE_DOCX:  raw_counts.get(MediaFile.TYPE_DOCX,  0),
        MediaFile.TYPE_EXCEL: raw_counts.get(MediaFile.TYPE_EXCEL, 0),
        MediaFile.TYPE_OTHER: raw_counts.get(MediaFile.TYPE_OTHER, 0),
    }
    total_all = sum(type_counts.values())

    context = {
        "page":        page,
        "type_filter": type_filter,
        "search":      search,
        "type_counts": type_counts,
        "type_choices": MediaFile.TYPE_CHOICES,
        "total_count":  qs.count(),
        "total_all":    total_all,
    }
    return render(request, "media_library/index.html", context)


@login_required
@require_POST
def upload(request):
    """
    Upload một hoặc nhiều file.
    Trả JSON:
      { "files": [{ "id", "name", "url", "file_type", "file_size_display" }, ...] }
    """
    uploaded = request.FILES.getlist("files") or request.FILES.getlist("file")
    if not uploaded:
        return JsonResponse({"error": "Không có file nào được gửi lên."}, status=400)

    max_bytes = MediaFile.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    results   = []
    errors    = []

    for f in uploaded:
        if f.size > max_bytes:
            errors.append(f"{f.name}: vượt quá {MediaFile.MAX_UPLOAD_SIZE_MB}MB")
            continue

        ext = os.path.splitext(f.name)[1].lower()
        if ext not in MediaFile.ALLOWED_EXTENSIONS:
            errors.append(f"{f.name}: định dạng không được hỗ trợ ({ext})")
            continue

        try:
            media = _save_media_file(f, request)
            results.append({
                "id":               media.pk,
                "name":             media.name,
                "url":              media.url,
                "file_type":        media.file_type,
                "file_size_display": media.file_size_display,
                "is_image":         media.is_image,
                "width":            media.width,
                "height":           media.height,
            })
        except Exception as exc:
            errors.append(f"{f.name}: {exc}")

    return JsonResponse({"files": results, "errors": errors})


@login_required
@require_POST
def upload_quill_image(request):
    """
    Endpoint riêng dành cho Quill image-paste handler.
    Nhận 1 file ảnh, trả JSON { "url": "..." } để Quill dùng làm src.
    Nếu lỗi trả { "error": "..." }.
    """
    f = request.FILES.get("image") or request.FILES.get("file")
    if not f:
        return JsonResponse({"error": "Không có file ảnh."}, status=400)

    max_bytes = MediaFile.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if f.size > max_bytes:
        return JsonResponse(
            {"error": f"Ảnh quá lớn (tối đa {MediaFile.MAX_UPLOAD_SIZE_MB}MB)."},
            status=400,
        )

    ext = os.path.splitext(f.name)[1].lower()
    allowed_img_exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    if ext not in allowed_img_exts:
        return JsonResponse({"error": f"Định dạng ảnh không hỗ trợ: {ext}"}, status=400)

    try:
        media = _save_media_file(f, request)
        return JsonResponse({"url": media.url, "id": media.pk})
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=500)


@login_required
@require_POST
def delete_file(request, pk: int):
    """Xóa file khỏi DB và storage."""
    media = get_object_or_404(MediaFile, pk=pk)

    # Xóa file vật lý
    try:
        if media.file and media.file.name:
            storage = media.file.storage
            if storage.exists(media.file.name):
                storage.delete(media.file.name)
    except Exception:
        pass  # Xóa DB record dù file vật lý có lỗi

    media.delete()
    return JsonResponse({"ok": True, "id": pk})


@login_required
def list_json(request):
    """
    JSON API cho media picker modal trong Quill.
    Params: ?type=image|pdf|docx|excel&q=search&page=1
    """
    type_filter = request.GET.get("type", "")
    search      = request.GET.get("q", "").strip()
    page_num    = int(request.GET.get("page", 1) or 1)
    per_page    = int(request.GET.get("per_page", 24) or 24)

    qs = MediaFile.objects.all()
    if type_filter:
        qs = qs.filter(file_type=type_filter)
    if search:
        qs = qs.filter(name__icontains=search)

    from django.core.paginator import Paginator
    paginator = Paginator(qs, per_page)
    page      = paginator.get_page(page_num)

    items = []
    for m in page.object_list:
        items.append({
            "id":                m.pk,
            "name":              m.name,
            "url":               m.url,
            "file_type":         m.file_type,
            "file_size_display": m.file_size_display,
            "is_image":          m.is_image,
            "width":             m.width,
            "height":            m.height,
            "alt_text":          m.alt_text,
        })

    return JsonResponse({
        "items":     items,
        "page":      page_num,
        "num_pages": paginator.num_pages,
        "has_next":  page.has_next(),
        "has_prev":  page.has_previous(),
        "total":     paginator.count,
    })

@login_required
def file_detail(request, pk: int):
    """Chi tiết một file (JSON) — dùng cho modal preview."""
    media = get_object_or_404(MediaFile, pk=pk)
    return JsonResponse({
        "id":               media.pk,
        "name":             media.name,
        "url":              media.url,
        "file_type":        media.file_type,
        "mime_type":        media.mime_type,
        "file_size_display": media.file_size_display,
        "is_image":         media.is_image,
        "width":            media.width,
        "height":           media.height,
        "alt_text":         media.alt_text,
        "note":             media.note,
        "created_at":       media.created_at.strftime("%d/%m/%Y %H:%M"),
        "created_by":       str(media.created_by) if media.created_by else "",
    })
