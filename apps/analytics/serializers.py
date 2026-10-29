from rest_framework import serializers


class CollectSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=['pageview', 'engagement'])
    event_id = serializers.UUIDField()
    visitor_id = serializers.UUIDField()
    session_id = serializers.UUIDField(required=False)
    path = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    title = serializers.CharField(required=False, allow_blank=True, max_length=500)
    referrer = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    channel = serializers.ChoiceField(choices=['web', 'app'], required=False, default='web')
    duration_ms = serializers.IntegerField(required=False, min_value=0)
    utm_source = serializers.CharField(required=False, allow_blank=True, max_length=200)
    utm_medium = serializers.CharField(required=False, allow_blank=True, max_length=200)
    utm_campaign = serializers.CharField(required=False, allow_blank=True, max_length=200)
    utm_content = serializers.CharField(required=False, allow_blank=True, max_length=200)
    utm_term = serializers.CharField(required=False, allow_blank=True, max_length=200)
    country = serializers.CharField(required=False, allow_blank=True, max_length=8)
    region = serializers.CharField(required=False, allow_blank=True, max_length=200)
    city = serializers.CharField(required=False, allow_blank=True, max_length=200)
