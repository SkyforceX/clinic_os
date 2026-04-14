# Coding rules
- Use service layer: services / selectors / policies
- Never call Model.objects directly, use tenant-aware manager
- Follow existing clinic_os architecture

# Tasks
- Always propose minimal patch
- Do not break legacy compatibility
- Keep template path unchanged

# Commands
- Run server: python manage.py runserver
- Run migrations: python manage.py migrate