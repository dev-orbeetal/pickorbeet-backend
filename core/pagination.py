"""Pagination helpers for admin and API list endpoints."""
from rest_framework.pagination import PageNumberPagination


class AdminPagination(PageNumberPagination):
    """Page-number pagination with a client-selectable page size."""

    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ProductAdminPagination(AdminPagination):
    """Product list can show a large page so similar names stay on one screen."""

    max_page_size = 500
