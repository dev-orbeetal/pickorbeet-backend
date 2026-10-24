from django.contrib import admin

from .models import Conversation, Message, SupportProfile


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('author', 'staff', 'body', 'topic', 'order', 'read_at', 'created_at')
    can_delete = False


@admin.register(SupportProfile)
class SupportProfileAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'reply_line', 'phone', 'email')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('customer', 'topic', 'customer_unread', 'staff_unread', 'last_message_at')
    inlines = [MessageInline]
