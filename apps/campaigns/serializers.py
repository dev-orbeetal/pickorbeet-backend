"""Admin and customer payloads for product-notification campaigns."""
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.products.models import Product

from .models import (
    AUDIENCE_CHOICES,
    KIND_CHOICES,
    AutomationRule,
    Campaign,
    CampaignSettings,
    CampaignTemplate,
)
from .rendering import PLACEHOLDERS

User = get_user_model()


class CampaignTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CampaignTemplate
        fields = ['id', 'kind', 'name', 'title', 'body', 'cta_label', 'is_recommended', 'is_system']
        read_only_fields = fields


class CampaignProductSerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'price', 'compare_price', 'image', 'category']
        read_only_fields = fields

    def get_image(self, product):
        from .images import image_url, product_thumbnail
        return image_url(product_thumbnail(product))


class CampaignSerializer(serializers.ModelSerializer):
    product = CampaignProductSerializer(read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default='')
    image_url = serializers.SerializerMethodField()
    opened = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Campaign
        fields = [
            'id', 'name', 'kind', 'source', 'trigger', 'title', 'body', 'cta_label',
            'product', 'product_ids', 'audience', 'customer_ids', 'context',
            'status', 'scheduled_for', 'started_at', 'finished_at',
            'recipients', 'pushed', 'opened', 'error', 'image_url',
            'created_by_name', 'created_at',
        ]
        read_only_fields = fields

    def get_image_url(self, campaign):
        from .dispatch import campaign_image_url
        return campaign_image_url(campaign, campaign.product)


class CampaignWriteSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    kind = serializers.ChoiceField(choices=KIND_CHOICES, required=False)
    title = serializers.CharField(max_length=80)
    body = serializers.CharField(max_length=240)
    cta_label = serializers.CharField(required=False, allow_blank=True, max_length=40)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    product_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    audience = serializers.ChoiceField(choices=AUDIENCE_CHOICES, required=False)
    customer_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    context = serializers.DictField(required=False)
    scheduled_for = serializers.DateTimeField(required=False, allow_null=True)


class PreviewSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=80)
    body = serializers.CharField(max_length=240)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    context = serializers.DictField(required=False)


class EstimateSerializer(serializers.Serializer):
    audience = serializers.ChoiceField(choices=AUDIENCE_CHOICES)
    product_id = serializers.UUIDField(required=False, allow_null=True)
    category_id = serializers.UUIDField(required=False, allow_null=True)
    customer_ids = serializers.ListField(child=serializers.UUIDField(), required=False)


class ScheduleSerializer(serializers.Serializer):
    when = serializers.DateTimeField()


class TestSendSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = [
            'trigger', 'enabled', 'title', 'body', 'digest_title', 'digest_body',
            'cta_label', 'audience', 'threshold',
        ]


class CampaignSettingsSerializer(serializers.ModelSerializer):
    placeholders = serializers.SerializerMethodField()

    class Meta:
        model = CampaignSettings
        fields = ['quiet_start', 'quiet_end', 'daily_cap', 'arrival_settle_minutes', 'placeholders']

    def get_placeholders(self, _settings):
        return PLACEHOLDERS


class CampaignCustomerSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'email', 'phone', 'full_name']
        read_only_fields = fields
