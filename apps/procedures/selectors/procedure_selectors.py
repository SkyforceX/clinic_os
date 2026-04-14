from ..models import Procedure, ProcedureStep, ProcedureAttachment


def get_procedures(filters=None):
    qs = Procedure.objects.select_related('created_by').order_by('-created_at')
    if not filters:
        return qs
    category = filters.get('category')
    status = filters.get('status')
    q = filters.get('q')
    if category:
        qs = qs.filter(category=category)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(title__icontains=q) | qs.filter(code__icontains=q)
    return qs


def get_procedure_by_id(procedure_id):
    return Procedure.objects.select_related('created_by').get(pk=procedure_id)


def get_steps_for_procedure(procedure_id):
    return (
        ProcedureStep.objects
        .filter(procedure_id=procedure_id)
        .prefetch_related('attachments')
        .order_by('order', 'pk')
    )


def get_attachments_for_procedure(procedure_id):
    return ProcedureAttachment.objects.filter(
        procedure_id=procedure_id, step__isnull=True,
    ).order_by('uploaded_at')
