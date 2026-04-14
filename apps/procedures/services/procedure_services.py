import os
from django.db import transaction
from django.db.models import Max

from ..models import Procedure, ProcedureStep, ProcedureAttachment


def create_procedure(data, user):
    with transaction.atomic():
        procedure = Procedure(
            title=data['title'],
            code=data.get('code', ''),
            category=data['category'],
            description=data.get('description', ''),
            status=data.get('status', 'draft'),
            version=data.get('version', '1.0'),
            effective_date=data.get('effective_date') or None,
            created_by=user,
        )
        procedure.save()
    return procedure


def update_procedure(procedure, data):
    with transaction.atomic():
        for field in ['title', 'code', 'category', 'description', 'status', 'version']:
            if field in data:
                setattr(procedure, field, data[field])
        procedure.effective_date = data.get('effective_date') or None
        procedure.save()
    return procedure


def _get_parent(procedure, parent_id):
    if not parent_id:
        return None
    try:
        return ProcedureStep.objects.get(pk=parent_id, procedure=procedure)
    except ProcedureStep.DoesNotExist:
        return None


def _is_descendant(potential_parent, step):
    visited = set()
    current = potential_parent
    while current is not None:
        if current.pk == step.pk:
            return True
        if current.pk in visited:
            break
        visited.add(current.pk)
        current = current.parent
    return False


def create_step(procedure, data):
    parent = _get_parent(procedure, data.get('parent_id'))
    max_order = ProcedureStep.objects.filter(
        procedure=procedure, parent=parent,
    ).aggregate(m=Max('order'))['m'] or 0

    return ProcedureStep.objects.create(
        procedure=procedure,
        parent=parent,
        title=data['title'],
        description=data.get('description', ''),
        responsible=data.get('responsible', ''),
        duration=data.get('duration', ''),
        order=max_order + 1,
        color=data.get('color', '#0d6efd'),
    )


def update_step(step, data):
    if 'parent_id' in data:
        raw_pid = data['parent_id']
        if raw_pid:
            candidate = _get_parent(step.procedure, raw_pid)
            if candidate and candidate.pk != step.pk and not _is_descendant(candidate, step):
                step.parent = candidate
            # else: silently keep current parent to avoid circular tree
        else:
            step.parent = None

    for field in ['title', 'description', 'responsible', 'duration', 'color', 'order']:
        if field in data:
            setattr(step, field, data[field])
    step.save()
    return step


def delete_step(step):
    ProcedureStep.objects.filter(parent=step).update(parent=step.parent)
    step.delete()


def upload_attachment(data, file, user):
    ext = os.path.splitext(file.name)[1].lower()
    if ext in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'):
        file_type = 'image'
    elif ext == '.pdf':
        file_type = 'pdf'
    else:
        file_type = 'other'

    return ProcedureAttachment.objects.create(
        procedure_id=data.get('procedure_id'),
        step_id=data.get('step_id') or None,
        name=data.get('name') or file.name,
        file=file,
        file_type=file_type,
        uploaded_by=user,
    )


def delete_attachment(attachment):
    try:
        attachment.file.delete(save=False)
    except Exception:
        pass
    attachment.delete()
