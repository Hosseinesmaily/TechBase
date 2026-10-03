from django.test import TestCase
from django.urls import reverse


class HealthTests(TestCase):
    def test_health_returns_ok(self) -> None:
        response = self.client.get(reverse("core:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_rejects_post(self) -> None:
        response = self.client.post(reverse("core:health"))
        self.assertEqual(response.status_code, 405)

    def test_ready_returns_structured_checks(self) -> None:
        response = self.client.get(reverse("core:ready"))
        # SQLite is always available during tests; Redis may not be.
        self.assertIn(response.status_code, (200, 503))
        body = response.json()
        self.assertIn("checks", body)
        self.assertIn("database", body["checks"])

    def test_homepage_smoke(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "techbase-api")
