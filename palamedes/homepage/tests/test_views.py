from django.test import TestCase, override_settings
from django.urls import reverse

from homepage.models import ChapterRequest
from palamedes.test_helpers import make_user

# base.html (extended by every homepage template) references {% static %}
# assets. STATICFILES_STORAGE is WhiteNoise's CompressedManifestStaticFilesStorage
# in settings.py, which requires a collectstatic-generated manifest that
# doesn't exist in this test environment. Swap to the plain storage backend
# for any test that renders a full page, or `{% static %}` raises
# ValueError: Missing staticfiles manifest entry (see codebase-notes.md §2).
_PLAIN_STATIC_STORAGE = override_settings(
    STATICFILES_STORAGE="django.contrib.staticfiles.storage.StaticFilesStorage"
)


@_PLAIN_STATIC_STORAGE
class HomeViewTests(TestCase):
    def test_anonymous_user_sees_landing_page(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homepage/home.html")

    def test_authenticated_user_is_redirected_to_dashboard(self):
        user = make_user()
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertRedirects(response, reverse("dashboard"))


@_PLAIN_STATIC_STORAGE
class AboutViewTests(TestCase):
    def test_renders_about_page_with_title(self):
        response = self.client.get(reverse("about"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homepage/about.html")
        self.assertEqual(response.context["title"], "About")


@_PLAIN_STATIC_STORAGE
class StartChapterViewTests(TestCase):
    def test_get_renders_empty_form(self):
        response = self.client.get(reverse("start_chapter"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homepage/start_chapter.html")
        self.assertFalse(response.context["form"].is_bound)

    def test_valid_post_creates_request_and_redirects_home(self):
        response = self.client.post(
            reverse("start_chapter"),
            data={
                "fraternity_name": "Theta Chi",
                "university": "UC Riverside",
                "president_email": "president@example.com",
            },
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(ChapterRequest.objects.count(), 1)
        req = ChapterRequest.objects.get()
        self.assertEqual(req.fraternity_name, "Theta Chi")

    def test_valid_post_adds_success_message(self):
        response = self.client.post(
            reverse("start_chapter"),
            data={
                "fraternity_name": "Theta Chi",
                "university": "UC Riverside",
                "president_email": "president@example.com",
            },
            follow=True,
        )
        messages = list(response.context["messages"])
        self.assertEqual(len(messages), 1)
        self.assertIn("submitted", str(messages[0]))

    def test_invalid_post_rerenders_form_with_errors(self):
        response = self.client.post(
            reverse("start_chapter"),
            data={
                "fraternity_name": "",
                "university": "UC Riverside",
                "president_email": "president@example.com",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "homepage/start_chapter.html")
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(ChapterRequest.objects.count(), 0)
