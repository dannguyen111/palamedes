from django.test import TestCase

from homepage.forms import ChapterRequestForm


class ChapterRequestFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "fraternity_name": "Theta Chi",
            "university": "UC Riverside",
            "president_email": "president@example.com",
        }
        data.update(overrides)
        return data

    def test_valid_data_is_valid(self):
        form = ChapterRequestForm(data=self.valid_data())
        self.assertTrue(form.is_valid())

    def test_missing_fraternity_name_is_invalid(self):
        form = ChapterRequestForm(data=self.valid_data(fraternity_name=""))
        self.assertFalse(form.is_valid())
        self.assertIn("fraternity_name", form.errors)

    def test_missing_university_is_invalid(self):
        form = ChapterRequestForm(data=self.valid_data(university=""))
        self.assertFalse(form.is_valid())
        self.assertIn("university", form.errors)

    def test_missing_president_email_is_invalid(self):
        form = ChapterRequestForm(data=self.valid_data(president_email=""))
        self.assertFalse(form.is_valid())
        self.assertIn("president_email", form.errors)

    def test_malformed_president_email_is_invalid(self):
        form = ChapterRequestForm(data=self.valid_data(president_email="not-an-email"))
        self.assertFalse(form.is_valid())
        self.assertIn("president_email", form.errors)

    def test_save_persists_chapter_request(self):
        form = ChapterRequestForm(data=self.valid_data())
        self.assertTrue(form.is_valid())
        req = form.save()
        self.assertEqual(req.fraternity_name, "Theta Chi")
        self.assertFalse(req.is_approved)
