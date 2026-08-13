from django.test import TestCase
from django.urls import reverse

from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user
from users.models import CustomUser


@PLAIN_STATIC_STORAGE
class AdminSmokeTests(TestCase):
    """PositionAdmin / ChapterAdmin / CustomUserAdmin are purely declarative
    (list_display/list_filter/search_fields/fieldsets only, no custom
    methods), so these tests exercise the changelist/add/change views end to
    end against real rows rather than just asserting registration."""

    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.superuser = CustomUser.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123!"
        )
        self.client.force_login(self.superuser)

    def test_chapter_changelist_renders(self):
        response = self.client.get(reverse("admin:users_chapter_changelist"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.chapter.name)

    def test_chapter_search_renders(self):
        response = self.client.get(reverse("admin:users_chapter_changelist"), {"q": "Riverside"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.chapter.name)

    def test_chapter_add_view_renders(self):
        response = self.client.get(reverse("admin:users_chapter_add"))
        self.assertEqual(response.status_code, 200)

    def test_chapter_change_view_renders(self):
        response = self.client.get(reverse("admin:users_chapter_change", args=[self.chapter.pk]))
        self.assertEqual(response.status_code, 200)

    def test_position_changelist_renders_and_filters_by_chapter(self):
        response = self.client.get(
            reverse("admin:users_position_changelist"), {"chapter__id__exact": self.chapter.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "President")

    def test_position_search_renders(self):
        response = self.client.get(reverse("admin:users_position_changelist"), {"q": "President"})
        self.assertEqual(response.status_code, 200)

    def test_position_change_view_renders(self):
        position = self.positions["President"]
        response = self.client.get(reverse("admin:users_position_change", args=[position.pk]))
        self.assertEqual(response.status_code, 200)

    def test_customuser_changelist_renders_and_filters(self):
        member = make_user(chapter=self.chapter, position=self.positions["No Position"], username="brother1")
        response = self.client.get(
            reverse("admin:users_customuser_changelist"),
            {"chapter__id__exact": self.chapter.pk, "status__exact": "ACT", "is_staff__exact": "0"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, member.username)

    def test_customuser_change_view_renders_with_fraternity_fieldset(self):
        member = make_user(chapter=self.chapter, position=self.positions["Treasurer"], username="brother2")
        response = self.client.get(reverse("admin:users_customuser_change", args=[member.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fraternity Info")

    def test_customuser_add_view_renders_with_fraternity_fieldset(self):
        response = self.client.get(reverse("admin:users_customuser_add"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fraternity Info")
