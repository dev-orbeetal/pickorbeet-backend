"""
URL configuration for Pickorbeet E-commerce project.
"""
from django.contrib import admin
from django.urls import path, include, re_path
from core.admin_panel import redirect_panel_path, serve_admin_panel
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
    openapi.Info(
        title="Pickorbeet E-commerce API",
        default_version='v1',
        description="API documentation for Pickorbeet E-commerce Platform",
        terms_of_service="https://www.pickorbeet.com/terms/",
        contact=openapi.Contact(email="contact@pickorbeet.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    # PickOrbeet admin panel (static export). Jazzmin stays available for models
    # the panel does not edit.
    re_path(r'^admin/(?P<path>.*)$', serve_admin_panel, name='admin_panel'),
    re_path(
        r'^(?P<page>login|dashboard|orders|products|categories|pos|coupons|inventory|barcode-labels|low-stock|reports|payments|staff|customers|contact|settings|money-management)(?P<rest>/.*)?$',
        redirect_panel_path,
    ),
    path('django-admin/', admin.site.urls),
    
    # API Documentation
    path('api/docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('api/redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # API Endpoints
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/products/', include('apps.products.urls')),
    path('api/v1/orders/', include('apps.orders.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/reports/', include('apps.reports.urls')),
    path('api/v1/shipping/', include('apps.shipping.urls')),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
