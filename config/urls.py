from django.conf import settings
from django.conf.urls import handler403, handler404, handler500
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView
from rest_framework.permissions import IsAdminUser

urlpatterns = [
    path("admin93/", admin.site.urls),

    # refactor apps
    path("org/", include("apps.organizations.urls")),
    path("patients/", include("apps.patients.urls")),
    path("patients-api/", include("apps.patients.api.urls")),
    path("contract/", include("apps.contract.urls", namespace="contract")),
    path("scheduling/", include("apps.scheduling.urls")),
    path("clinical/", include("apps.clinical.urls")),

    # legacy / transitional apps
    path("booking/", include("apps.booking.urls", namespace="booking")),
    path("quality/", include("apps.quality.urls", namespace="quality")),
    path("profile/", include("apps.account.urls", namespace="account")),
    path("", include("apps.authentication.urls", namespace="authentication")),

    # api his
    path("api/", include("apps.api_his.urls")),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[IsAdminUser]),
        name="schema",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.RESULTS_URL, document_root=settings.RESULTS_ROOT)

handler403 = "apps.core.views.custom_permission_denied"
handler404 = "apps.core.views.custom_page_not_found"
handler500 = "apps.core.views.custom_server_error"