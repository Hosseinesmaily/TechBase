from __future__ import annotations

from rest_framework import serializers

from .models import CompatibilityRule


class CompatibilityRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompatibilityRule
        fields = (
            "id",
            "code",
            "category_a",
            "category_b",
            "description",
            "description_fa",
            "params",
            "enabled",
            "severity",
            "order",
        )
        read_only_fields = fields


class CompatibilityCheckRequestSerializer(serializers.Serializer):
    """`POST /compat/check/` body: a list of entity slugs."""

    parts = serializers.ListField(
        child=serializers.SlugField(),
        allow_empty=False,
        max_length=20,
        help_text="Entity slugs to check, e.g. ['ryzen-7-7800x3d', 'b650-tomahawk'].",
    )


class FindingSerializer(serializers.Serializer):
    rule_code = serializers.CharField()
    severity = serializers.ChoiceField(choices=["block", "warn", "info"])
    message = serializers.CharField()
    message_fa = serializers.CharField()
    a = serializers.DictField()
    b = serializers.DictField()


class CompatibilityCheckResponseSerializer(serializers.Serializer):
    verdict = serializers.ChoiceField(choices=["ok", "warn", "block"])
    findings = FindingSerializer(many=True)
    checked = serializers.ListField(child=serializers.CharField())
