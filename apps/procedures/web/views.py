import json

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib import messages

from ..models import Procedure, ProcedureStep, ProcedureAttachment
from ..policies import (
    can_view_procedures, can_create_procedure, can_edit_procedure,
    can_delete_procedure, can_publish_procedure,
)
from ..selectors.procedure_selectors import (
    get_procedures, get_steps_for_procedure, get_attachments_for_procedure,
)
from ..services.procedure_services import (
    create_procedure, update_procedure,
    create_step, update_step, delete_step,
    upload_attachment, delete_attachment,
)


@login_required
def procedure_list(request):
    if not can_view_procedures(request.user):
        messages.error(request, 'Bạn không có quyền truy cập.')
        return redirect('dashboard:index')

    filters = {
        'category': request.GET.get('category', ''),
        'status': request.GET.get('status', ''),
        'q': request.GET.get('q', ''),
    }
    procedures = get_procedures(filters)

    return render(request, 'procedures/staff/list.html', {
        'procedures': procedures,
        'filters': filters,
        'category_choices': Procedure.CATEGORY_CHOICES,
        'status_choices': Procedure.STATUS_CHOICES,
        'can_create': can_create_procedure(request.user),
    })


@login_required
def procedure_create(request):
    if not can_create_procedure(request.user):
        messages.error(request, 'Bạn không có quyền tạo quy trình.')
        return redirect('procedures:list')

    if request.method == 'POST':
        data = {
            'title': request.POST.get('title', '').strip(),
            'code': request.POST.get('code', '').strip(),
            'category': request.POST.get('category', 'other'),
            'description': request.POST.get('description', ''),
            'status': request.POST.get('status', 'draft'),
            'version': request.POST.get('version', '1.0'),
            'effective_date': request.POST.get('effective_date', ''),
        }
        if not data['title']:
            messages.error(request, 'Vui lòng nhập tên quy trình.')
        else:
            try:
                proc = create_procedure(data, request.user)
                messages.success(request, f'Đã tạo quy trình "{proc.title}".')
                return redirect('procedures:detail', pk=proc.pk)
            except Exception as exc:
                messages.error(request, f'Lỗi: {exc}')

    return render(request, 'procedures/staff/create_edit.html', {
        'procedure': None,
        'category_choices': Procedure.CATEGORY_CHOICES,
        'status_choices': Procedure.STATUS_CHOICES,
        'is_edit': False,
    })


@login_required
def procedure_edit(request, pk):
    procedure = get_object_or_404(Procedure, pk=pk)
    if not can_edit_procedure(request.user, procedure):
        messages.error(request, 'Bạn không có quyền chỉnh sửa quy trình này.')
        return redirect('procedures:detail', pk=pk)

    if request.method == 'POST':
        data = {
            'title': request.POST.get('title', '').strip(),
            'code': request.POST.get('code', '').strip(),
            'category': request.POST.get('category', 'other'),
            'description': request.POST.get('description', ''),
            'status': request.POST.get('status', 'draft'),
            'version': request.POST.get('version', '1.0'),
            'effective_date': request.POST.get('effective_date', ''),
        }
        if not data['title']:
            messages.error(request, 'Vui lòng nhập tên quy trình.')
        else:
            try:
                procedure = update_procedure(procedure, data)
                messages.success(request, 'Đã cập nhật quy trình.')
                return redirect('procedures:detail', pk=pk)
            except Exception as exc:
                messages.error(request, f'Lỗi: {exc}')

    return render(request, 'procedures/staff/create_edit.html', {
        'procedure': procedure,
        'category_choices': Procedure.CATEGORY_CHOICES,
        'status_choices': Procedure.STATUS_CHOICES,
        'is_edit': True,
    })


@login_required
def procedure_detail(request, pk):
    procedure = get_object_or_404(Procedure, pk=pk)
    if not can_view_procedures(request.user):
        messages.error(request, 'Bạn không có quyền xem quy trình.')
        return redirect('procedures:list')

    steps = get_steps_for_procedure(pk)
    attachments = get_attachments_for_procedure(pk)
    steps_json = json.dumps([s.to_dict() for s in steps])
    step_choices_json = json.dumps([{'id': s.pk, 'title': s.title} for s in steps])

    return render(request, 'procedures/staff/detail.html', {
        'procedure': procedure,
        'steps': steps,
        'attachments': attachments,
        'steps_json': steps_json,
        'step_choices_json': step_choices_json,
        'color_choices': ProcedureStep.COLOR_CHOICES,
        'can_edit': can_edit_procedure(request.user, procedure),
        'can_delete': can_delete_procedure(request.user, procedure),
        'can_publish': can_publish_procedure(request.user),
    })


@login_required
@require_POST
def procedure_delete(request, pk):
    procedure = get_object_or_404(Procedure, pk=pk)
    if not can_delete_procedure(request.user, procedure):
        messages.error(request, 'Bạn không có quyền xóa quy trình này.')
        return redirect('procedures:detail', pk=pk)
    title = procedure.title
    procedure.delete()
    messages.success(request, f'Đã xóa quy trình "{title}".')
    return redirect('procedures:list')


# ── STEP AJAX VIEWS ───────────────────────────────────────────────────────────

@login_required
@require_POST
def step_create(request, procedure_pk):
    procedure = get_object_or_404(Procedure, pk=procedure_pk)
    if not can_edit_procedure(request.user, procedure):
        return JsonResponse({'error': 'Không có quyền'}, status=403)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        body = request.POST.dict()

    if not str(body.get('title', '')).strip():
        return JsonResponse({'error': 'Tiêu đề không được để trống'}, status=400)

    step = create_step(procedure, body)
    all_steps = list(get_steps_for_procedure(procedure_pk))
    return JsonResponse({
        'ok': True,
        'step': step.to_dict(),
        'all_steps': [s.to_dict() for s in all_steps],
    })


@login_required
@require_POST
def step_edit(request, step_pk):
    step = get_object_or_404(ProcedureStep, pk=step_pk)
    if not can_edit_procedure(request.user, step.procedure):
        return JsonResponse({'error': 'Không có quyền'}, status=403)
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        body = request.POST.dict()

    step = update_step(step, body)
    all_steps = list(get_steps_for_procedure(step.procedure_id))
    return JsonResponse({
        'ok': True,
        'step': step.to_dict(),
        'all_steps': [s.to_dict() for s in all_steps],
    })


@login_required
@require_POST
def step_delete(request, step_pk):
    step = get_object_or_404(ProcedureStep, pk=step_pk)
    if not can_edit_procedure(request.user, step.procedure):
        return JsonResponse({'error': 'Không có quyền'}, status=403)
    procedure_id = step.procedure_id
    delete_step(step)
    all_steps = list(get_steps_for_procedure(procedure_id))
    return JsonResponse({'ok': True, 'all_steps': [s.to_dict() for s in all_steps]})


# ── ATTACHMENT AJAX VIEWS ─────────────────────────────────────────────────────

@login_required
@require_POST
def attachment_upload(request, procedure_pk):
    procedure = get_object_or_404(Procedure, pk=procedure_pk)
    if not can_edit_procedure(request.user, procedure):
        return JsonResponse({'error': 'Không có quyền'}, status=403)

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'Không có tệp được chọn'}, status=400)

    data = {
        'procedure_id': procedure.pk,
        'step_id': request.POST.get('step_id') or None,
        'name': request.POST.get('name', '').strip() or file.name,
    }
    attachment = upload_attachment(data, file, request.user)
    return JsonResponse({'ok': True, 'attachment': attachment.to_dict()})


@login_required
@require_POST
def attachment_delete(request, attachment_pk):
    attachment = get_object_or_404(ProcedureAttachment, pk=attachment_pk)
    procedure = attachment.procedure or (attachment.step.procedure if attachment.step else None)
    if procedure and not can_edit_procedure(request.user, procedure):
        return JsonResponse({'error': 'Không có quyền'}, status=403)
    delete_attachment(attachment)
    return JsonResponse({'ok': True})
