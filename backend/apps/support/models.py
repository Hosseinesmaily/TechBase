"""Support tickets: a customer asks a question, the team answers it.

Only the owner and the staff can read a ticket. That is enforced where the
tickets are queried (`api.py`), never by hiding a link: a guessed id returns
404 instead of somebody else's conversation.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class TicketStatus(models.TextChoices):
    """Where a ticket stands. Persian labels: they are shown in the admin."""

    OPEN = "open", "باز"
    IN_PROGRESS = "in_progress", "در حال بررسی"
    ANSWERED = "answered", "پاسخ دادهشده"
    CLOSED = "closed", "بسته"


class Ticket(UUIDModel, TimeStampedModel):
    """One support thread, opened by a signed-in customer.

    The primary key is a UUID on purpose: the id travels in an URL the customer
    can see, and a non-guessable id is one less way to reach a stranger's thread.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="support_tickets",
        verbose_name="کاربر",
    )
    subject = models.CharField(max_length=200, verbose_name="عنوان")
    status = models.CharField(
        max_length=16,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True,
        verbose_name="وضعیت",
    )
    #: The moment of the newest message, so both panels can sort by activity.
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = "تیکت پشتیبانی"
        verbose_name_plural = "تیکتهای پشتیبانی"
        ordering = ["-last_message_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "status"], name="ticket_user_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.subject} — {self.get_status_display()}"

    @property
    def has_staff_reply(self) -> bool:
        return self.messages.filter(from_staff=True).exists()


class TicketMessage(UUIDModel, TimeStampedModel):
    """One message in a thread: written by the customer or by the staff."""

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="messages", verbose_name="تیکت"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="support_messages",
        verbose_name="نویسنده",
    )
    body = models.TextField(verbose_name="متن پیام")
    #: True for a message written from the support side of the thread.
    from_staff = models.BooleanField(default=False, db_index=True, verbose_name="از پشتیبانی")

    class Meta:
        verbose_name = "پیام تیکت"
        verbose_name_plural = "پیامهای تیکت"
        ordering = ["created_at"]

    def __str__(self) -> str:
        side = "پشتیبانی" if self.from_staff else "کاربر"
        return f"{side}: {self.body[:40]}"
