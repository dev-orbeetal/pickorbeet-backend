from django.urls import path

from .views import (
    AdminCareerApplicationDetailView,
    AdminCareerApplicationListView,
    CareerApplicationFileView,
    PublicCareerApplyView,
)

urlpatterns = [
    path('apply/', PublicCareerApplyView.as_view(), name='career_apply'),
    path('admin/applications/', AdminCareerApplicationListView.as_view(), name='admin_career_list'),
    path(
        'admin/applications/<uuid:pk>/',
        AdminCareerApplicationDetailView.as_view(),
        name='admin_career_detail',
    ),
    path(
        'admin/applications/<uuid:pk>/cv/',
        CareerApplicationFileView.as_view(),
        {'kind': 'cv'},
        name='admin_career_cv',
    ),
    path(
        'admin/applications/<uuid:pk>/picture/',
        CareerApplicationFileView.as_view(),
        {'kind': 'picture'},
        name='admin_career_picture',
    ),
]
