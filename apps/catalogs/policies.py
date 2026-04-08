class CatalogPolicy:
    MANAGER_GROUP_NAMES = {"Executive", "IT Admin"}
    SALES_GROUP_NAMES = {"Sales Team"}

    @classmethod
    def is_authenticated_actor(cls, user):
        return bool(user and user.is_authenticated)

    @classmethod
    def is_manager(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        if getattr(user, "is_superuser", False):
            return True
        return user.groups.filter(name__in=cls.MANAGER_GROUP_NAMES).exists()

    @classmethod
    def is_sales(cls, user):
        if not cls.is_authenticated_actor(user):
            return False
        return user.groups.filter(name__in=cls.SALES_GROUP_NAMES).exists()

    @classmethod
    def can_manage_groups(cls, user):
        return cls.is_manager(user) or cls.is_sales(user)

    @classmethod
    def can_manage_categories(cls, user):
        return cls.is_it_admin(user) or cls.is_sales(user)

    @classmethod
    def can_view_packages(cls, user):
        return cls.is_executive(user) or cls.is_sales(user)

    @classmethod
    def can_create_package(cls, user):
        return cls.is_it_admin(user) or cls.is_sales(user)

    @classmethod
    def can_edit_package(cls, user, package):
        if not cls.is_authenticated_actor(user):
            return False
        if cls.is_manager(user):
            return True
        return getattr(package, "created_by_id", None) == user.id

    @classmethod
    def can_delete_package(cls, user, package):
        return cls.can_edit_package(user, package)