"""
Public Bangladesh location catalog endpoints for cascading address selectors.
"""
from django.db.models import Q
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import BdDistrict, BdDivision, BdPostOffice
from apps.accounts.serializers import (
    BdDistrictSerializer,
    BdDivisionSerializer,
    BdPostOfficeSerializer,
)


class BdDivisionListView(generics.ListAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = BdDivisionSerializer
    pagination_class = None
    queryset = BdDivision.objects.all()


class BdDistrictListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        division = (request.query_params.get('division') or '').strip()
        if not division:
            return Response({'detail': 'Query param division is required.'}, status=400)
        qs = BdDistrict.objects.select_related('division')
        if len(division) == 36 and division.count('-') == 4:
            qs = qs.filter(division_id=division)
        else:
            qs = qs.filter(Q(division__slug=division) | Q(division__name__iexact=division))
        return Response(BdDistrictSerializer(qs.distinct().order_by('name'), many=True).data)


class BdPostOfficeListView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        district = (request.query_params.get('district') or '').strip()
        if not district:
            return Response({'detail': 'Query param district is required.'}, status=400)
        qs = BdPostOffice.objects.select_related('district')
        if len(district) == 36 and district.count('-') == 4:
            qs = qs.filter(district_id=district)
        else:
            qs = qs.filter(Q(district__slug=district) | Q(district__name__iexact=district))
        return Response(
            BdPostOfficeSerializer(qs.distinct().order_by('name', 'postal_code'), many=True).data
        )
