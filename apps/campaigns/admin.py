from django.contrib import admin

from .models import AutomationRule, Campaign, CampaignSettings, CampaignTemplate, ProductWatch


@admin.register(CampaignTemplate)
class CampaignTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'is_recommended', 'is_system')
    list_filter = ('kind',)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'status', 'source', 'recipients', 'pushed', 'created_at')
    list_filter = ('kind', 'status', 'source')
    readonly_fields = ('recipients', 'pushed', 'started_at', 'finished_at', 'error')


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = ('trigger', 'enabled', 'audience', 'threshold')


@admin.register(CampaignSettings)
class CampaignSettingsAdmin(admin.ModelAdmin):
    list_display = ('quiet_start', 'quiet_end', 'daily_cap', 'arrival_settle_minutes')


@admin.register(ProductWatch)
class ProductWatchAdmin(admin.ModelAdmin):
    list_display = ('product', 'announced_at', 'units', 'available', 'price', 'primed')
    readonly_fields = ('checked_at',)
