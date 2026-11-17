"""The Django admin view of the support desk.

It exists next to the site's own panel because it is the tool the staff already
has: filtering by status, reading a thread inline and answering it in place.
"""

from __future__ import annotations

from django.contrib import admin
from django.utils import timezone

from .models import Ticket, TicketMessage, TicketStatus


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 1
    fields = ("created_at", "from_staff", "author", "body")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("author",)
    verbose_name = "پیام"
    verbose_name_plural = "پیامهای تیکت"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "status", "last_message_at", "created_at")
    list_filter = ("status",)
    search_fields = ("subject", "user__email", "user__username", "messages__body")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at", "updated_at", "last_message_at")
    date_hierarchy = "created_at"
    inlines = (TicketMessageInline,)

    @admin.action(description="انتقال به «در حال بررسی»")
    def mark_in_progress(self, request, queryset):
        queryset.update(status=TicketStatus.IN_PROGRESS, updated_at=timezone.now())

    @admin.action(description="علامتگذاری بهعنوان «پاسخ دادهشده»")
    def mark_answered(self, request, queryset):
        queryset.update(status=TicketStatus.ANSWERED, updated_at=timezone.now())

    @admin.action(description="بستن تیکتهای انتخابشده")
    def mark_closed(self, request, queryset):
        queryset.update(status=TicketStatus.CLOSED, updated_at=timezone.now())

    actions = ("mark_in_progress", "mark_answered", "mark_closed")
