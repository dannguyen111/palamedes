from django.test import TestCase

from homepage.models import ChapterRequest


class ChapterRequestModelTests(TestCase):
    def test_str_includes_fraternity_name_and_university(self):
        req = ChapterRequest.objects.create(
            fraternity_name="Theta Chi",
            university="UC Riverside",
            president_email="president@example.com",
        )
        self.assertEqual(str(req), "Theta Chi at UC Riverside")

    def test_is_approved_defaults_to_false(self):
        req = ChapterRequest.objects.create(
            fraternity_name="Theta Chi",
            university="UC Riverside",
            president_email="president@example.com",
        )
        self.assertFalse(req.is_approved)

    def test_date_requested_auto_populates_on_create(self):
        req = ChapterRequest.objects.create(
            fraternity_name="Theta Chi",
            university="UC Riverside",
            president_email="president@example.com",
        )
        self.assertIsNotNone(req.date_requested)

    def test_can_be_marked_approved(self):
        req = ChapterRequest.objects.create(
            fraternity_name="Theta Chi",
            university="UC Riverside",
            president_email="president@example.com",
            is_approved=True,
        )
        self.assertTrue(req.is_approved)
