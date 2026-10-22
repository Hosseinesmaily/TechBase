"""Compatibility API.

`POST /compat/check/` is public: the configurator and the assistant both use it.
`GET /compat/rules/` is staff-only (rule introspection = transparency).
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CompatibilityRule
from .serializers import (
    CompatibilityCheckRequestSerializer,
    CompatibilityRuleSerializer,
)
from .services import check_parts


class CompatibilityCheckView(APIView):
    """Check whether a set of parts works together.

    The verdict and every finding come from the deterministic rule engine —
    never from a model.
    """

    def post(self, request) -> Response:
        serializer = CompatibilityCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = check_parts(serializer.validated_data["parts"])
        return Response(report.as_dict(), status=status.HTTP_200_OK)


class CompatibilityRuleListView(APIView):
    """List the active rules. Staff only — this exposes engine internals."""

    permission_classes = [IsAdminUser]

    def get(self, request) -> Response:
        rules = CompatibilityRule.objects.order_by("order", "code")
        return Response(CompatibilityRuleSerializer(rules, many=True).data)
