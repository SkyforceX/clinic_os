from apps.contract.models.document import DocumentTemplate


def get_active_document_template(doc_type: str):
    return (
        DocumentTemplate.objects.filter(doc_type=doc_type, is_active=True)
        .order_by("-updated_at", "-id")
        .first()
    )