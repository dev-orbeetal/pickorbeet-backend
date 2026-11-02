"""Public geo catalog routes."""
from django.urls import path

from apps.accounts.geo_views import BdDistrictListView, BdDivisionListView, BdPostOfficeListView

urlpatterns = [
    path('divisions/', BdDivisionListView.as_view(), name='bd_divisions'),
    path('districts/', BdDistrictListView.as_view(), name='bd_districts'),
    path('post-offices/', BdPostOfficeListView.as_view(), name='bd_post_offices'),
]
