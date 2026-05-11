from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from gateway.views import HealthView, SchemaAggregateView

urlpatterns = [
    # Infrastructure
    path('health/', HealthView.as_view(), name='health'),

    # Gateway-level OpenAPI schema (describes the gateway's own proxy endpoints)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Aggregated schema fetched from all downstream services
    path('api/schema/aggregate/', SchemaAggregateView.as_view(), name='schema-aggregate'),

    # All /api/v1/<service-prefix>/... requests are proxied to downstream services
    path('api/v1/', include('gateway.urls')),
]
