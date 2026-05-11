from django.urls import re_path

from .views import ProxyView

# Captures the service prefix (e.g. "appointments") and the remainder of the path.
# The trailing slash on the prefix segment is required; path may be empty.
urlpatterns = [
    re_path(
        r'^(?P<prefix>[a-z][a-z0-9-]*)/(?P<path>.*)$',
        ProxyView.as_view(),
        name='proxy',
    ),
]
