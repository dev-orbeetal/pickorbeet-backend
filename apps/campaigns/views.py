"""Staff compose, send and automate product notifications. Customers keep a wishlist."""
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSeller
from apps.products.models import Category, Product, WishlistItem
from core.pagination import AdminPagination

from .dispatch import CampaignError
from .models import AutomationRule, Campaign, CampaignSettings, CampaignTemplate
from .serializers import (
    AutomationRuleSerializer,
    CampaignCustomerSerializer,
    CampaignSerializer,
    CampaignSettingsSerializer,
    CampaignTemplateSerializer,
    CampaignWriteSerializer,
    EstimateSerializer,
    PreviewSerializer,
    ScheduleSerializer,
    TestSendSerializer,
)
from .services import (
    attach_image,
    cancel,
    estimate,
    preview,
    save_campaign,
    schedule,
    send_now,
    test_send,
)

User = get_user_model()
WISHLIST_CAP = 50


def _error(exc):
    return Response({'error': exc.message, 'code': exc.code}, status=exc.http_status)


class TemplateListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsSeller]
    serializer_class = CampaignTemplateSerializer
    pagination_class = None
    queryset = CampaignTemplate.objects.all()


class CampaignListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsSeller]
    serializer_class = CampaignSerializer
    pagination_class = AdminPagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = (
            Campaign.objects.select_related('product', 'product__category', 'created_by')
            .prefetch_related('product__images', 'product__variants')
            .annotate(opened=Count('notifications', filter=Q(notifications__read_at__isnull=False)))
        )
        kind = self.request.query_params.get('kind')
        status_filter = self.request.query_params.get('status')
        if kind:
            queryset = queryset.filter(kind=kind)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = CampaignWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            campaign = save_campaign(serializer.validated_data, user=request.user)
        except CampaignError as exc:
            return _error(exc)
        image = request.FILES.get('image')
        if image:
            attach_image(campaign, image)
        when = serializer.validated_data.get('scheduled_for')
        if when:
            try:
                campaign = schedule(campaign, when)
            except CampaignError as exc:
                return _error(exc)
        return Response(CampaignSerializer(campaign).data, status=status.HTTP_201_CREATED)


class CampaignDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsSeller]
    serializer_class = CampaignSerializer
    parser_classes = [JSONParser, MultiPartParser, FormParser]
    queryset = Campaign.objects.select_related('product', 'product__category', 'created_by').prefetch_related(
        'product__images', 'product__variants',
    )

    def update(self, request, *args, **kwargs):
        campaign = self.get_object()
        serializer = CampaignWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # PATCH may omit title/body; keep what is already on the campaign.
        data.setdefault('title', campaign.title)
        data.setdefault('body', campaign.body)
        try:
            campaign = save_campaign(data, user=request.user, campaign=campaign)
        except CampaignError as exc:
            return _error(exc)
        image = request.FILES.get('image')
        if image:
            attach_image(campaign, image)
        return Response(CampaignSerializer(campaign).data)


class CampaignSendView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request, pk):
        campaign = generics.get_object_or_404(Campaign, pk=pk)
        try:
            campaign = send_now(campaign)
        except CampaignError as exc:
            return _error(exc)
        return Response(CampaignSerializer(campaign).data)


class CampaignScheduleView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request, pk):
        campaign = generics.get_object_or_404(Campaign, pk=pk)
        serializer = ScheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            campaign = schedule(campaign, serializer.validated_data['when'])
        except CampaignError as exc:
            return _error(exc)
        return Response(CampaignSerializer(campaign).data)


class CampaignCancelView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request, pk):
        campaign = generics.get_object_or_404(Campaign, pk=pk)
        try:
            campaign = cancel(campaign)
        except CampaignError as exc:
            return _error(exc)
        return Response(CampaignSerializer(campaign).data)


class CampaignTestView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request, pk):
        campaign = generics.get_object_or_404(
            Campaign.objects.select_related('product', 'product__category').prefetch_related(
                'product__images', 'product__variants',
            ),
            pk=pk,
        )
        serializer = TestSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer = generics.get_object_or_404(
            User, pk=serializer.validated_data['customer_id'], role='customer',
        )
        try:
            notification, created = test_send(campaign, customer)
        except CampaignError as exc:
            return _error(exc)
        return Response({
            'sent': created,
            'notification_id': str(notification.id),
            'customer_id': str(customer.id),
        })


class CampaignPreviewView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request):
        serializer = PreviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = None
        product_id = serializer.validated_data.get('product_id')
        if product_id:
            product = Product.objects.filter(pk=product_id).prefetch_related('images', 'variants').select_related('category').first()
        try:
            return Response(preview(
                title=serializer.validated_data['title'],
                body=serializer.validated_data['body'],
                product=product,
                context=serializer.validated_data.get('context') or {},
            ))
        except CampaignError as exc:
            return _error(exc)


class CampaignEstimateView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def post(self, request):
        serializer = EstimateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = Product.objects.filter(pk=serializer.validated_data.get('product_id')).first()
        category = Category.objects.filter(pk=serializer.validated_data.get('category_id')).first()
        try:
            return Response(estimate(
                audience=serializer.validated_data['audience'],
                product=product,
                category=category,
                customer_ids=serializer.validated_data.get('customer_ids') or [],
            ))
        except CampaignError as exc:
            return _error(exc)


class AutomationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsSeller]
    serializer_class = AutomationRuleSerializer
    pagination_class = None
    queryset = AutomationRule.objects.all()


class AutomationDetailView(generics.UpdateAPIView):
    permission_classes = [IsAuthenticated, IsSeller]
    serializer_class = AutomationRuleSerializer
    queryset = AutomationRule.objects.all()
    lookup_field = 'trigger'


class SettingsView(APIView):
    permission_classes = [IsAuthenticated, IsSeller]

    def get(self, request):
        return Response(CampaignSettingsSerializer(CampaignSettings.load()).data)

    def patch(self, request):
        settings = CampaignSettings.load()
        serializer = CampaignSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CampaignCustomerSearchView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsSeller]
    serializer_class = CampaignCustomerSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        queryset = User.objects.filter(role='customer', is_active=True).order_by('first_name', 'last_name')
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) | Q(last_name__icontains=search) |
                Q(email__icontains=search) | Q(phone__icontains=search)
            )
        return queryset


class WishlistView(APIView):
    """The signed-in customer's saved products. The phone keeps its own copy and puts it here."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        ids = list(
            WishlistItem.objects.filter(user=request.user).order_by('-created_at').values_list('product_id', flat=True)
        )
        return Response({'product_ids': [str(value) for value in ids]})

    def put(self, request):
        raw = request.data.get('product_ids') or []
        if not isinstance(raw, list):
            return Response({'error': 'Send product_ids as a list.'}, status=status.HTTP_400_BAD_REQUEST)
        wanted = []
        seen = set()
        for value in raw[:WISHLIST_CAP]:
            key = str(value)
            if key in seen:
                continue
            seen.add(key)
            wanted.append(key)
        known = {
            str(pk) for pk in Product.objects.filter(pk__in=wanted).values_list('pk', flat=True)
        }
        ordered = [value for value in wanted if value in known]
        WishlistItem.objects.filter(user=request.user).exclude(product_id__in=ordered).delete()
        have = {
            str(pk) for pk in WishlistItem.objects.filter(user=request.user).values_list('product_id', flat=True)
        }
        WishlistItem.objects.bulk_create(
            [WishlistItem(user=request.user, product_id=product_id) for product_id in ordered if product_id not in have],
            ignore_conflicts=True,
        )
        return self.get(request)


class WishlistItemView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, pk):
        if not Product.objects.filter(pk=pk).exists():
            return Response({'error': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)
        if (
            not WishlistItem.objects.filter(user=request.user, product_id=pk).exists()
            and WishlistItem.objects.filter(user=request.user).count() >= WISHLIST_CAP
        ):
            return Response({'error': 'Wishlist is full.', 'code': 'full'}, status=status.HTTP_400_BAD_REQUEST)
        WishlistItem.objects.get_or_create(user=request.user, product_id=pk)
        return Response({'saved': True})

    def delete(self, request, pk):
        WishlistItem.objects.filter(user=request.user, product_id=pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


