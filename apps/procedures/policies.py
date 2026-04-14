MANAGER_GROUPS = {'Executives', 'Executive', 'Managers', 'Manager', 'Quality'}
EDITOR_GROUPS = {'Executives', 'Executive', 'Managers', 'Manager', 'Quality', 'HR Admins', 'HR Admin'}


def can_view_procedures(user):
    return user.is_authenticated


def can_create_procedure(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_groups = set(user.groups.values_list('name', flat=True))
    return bool(user_groups & EDITOR_GROUPS)


def can_edit_procedure(user, procedure):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_groups = set(user.groups.values_list('name', flat=True))
    if user_groups & MANAGER_GROUPS:
        return True
    return procedure.created_by_id == user.pk


def can_delete_procedure(user, procedure):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_groups = set(user.groups.values_list('name', flat=True))
    return bool(user_groups & {'Executives', 'Executive', 'Managers', 'Manager'})


def can_publish_procedure(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_groups = set(user.groups.values_list('name', flat=True))
    return bool(user_groups & MANAGER_GROUPS)
