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
from .services import check_parts, evaluate_candidates


class CompatibilityCheckView(APIView):
    """Check whether a set of parts works together.

    The verdict and every finding come from the deterministic rule engine —
    never from a model. When `candidates` is given, each one is also evaluated
    against `parts` (that is what the configurator badges its cards with).
    """

    def post(self, request) -> Response:
        serializer = CompatibilityCheckRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        parts = serializer.validated_data["parts"]
        report = check_parts(parts)
        payload = report.as_dict()

        candidates = serializer.validated_data.get("candidates") or []
        if candidates:
            payload["candidate_results"] = evaluate_candidates(parts, candidates)

        return Response(payload, status=status.HTTP_200_OK)


class CompatibilityRuleListView(APIView):
    """List the active rules. Staff only — this exposes engine internals."""

    permission_classes = [IsAdminUser]

    def get(self, request) -> Response:
        rules = CompatibilityRule.objects.order_by("order", "code")
        return Response(CompatibilityRuleSerializer(rules, many=True).data)
