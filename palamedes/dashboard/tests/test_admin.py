from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from dashboard.models import Announcement, Due, HousePoint, Task
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user
from users.models import CustomUser


@PLAIN_STATIC_STORAGE
class AdminSmokeTests(TestCase):
    """HousePointAdmin / DueAdmin / TaskAdmin / AnnouncementAdmin are purely
    declarative (list_display/list_filter/search_fields only, no custom
    methods), so these tests exercise the changelist/change views end to end
    against real rows rather than just asserting registration."""

    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.member = make_user(chapter=self.chapter, position=self.positions["No Position"], username="brother1")
        self.superuser = CustomUser.objects.create_superuser(
            username="admin", email="admin@example.com", password="testpass123!"
        )
        self.client.force_login(self.superuser)

    def test_housepoint_changelist_renders_and_filters(self):
        HousePoint.objects.create(
            user=self.member, chapter=self.chapter, submitted_by=self.member, amount=5, description="Attended event"
        )
        response = self.client.get(
            reverse("admin:dashboard_housepoint_changelist"),
            {"status__exact": "PENDING", "chapter__id__exact": self.chapter.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.username)

    def test_housepoint_search_renders(self):
        HousePoint.objects.create(
            user=self.member, chapter=self.chapter, submitted_by=self.member, amount=5, description="Attended event"
        )
        response = self.client.get(reverse("admin:dashboard_housepoint_changelist"), {"q": self.member.username})
        self.assertEqual(response.status_code, 200)

    def test_housepoint_change_view_renders(self):
        point = HousePoint.objects.create(
            user=self.member, chapter=self.chapter, submitted_by=self.member, amount=5, description="Attended event"
        )
        response = self.client.get(reverse("admin:dashboard_housepoint_change", args=[point.pk]))
        self.assertEqual(response.status_code, 200)

    def test_due_changelist_renders_and_filters(self):
        Due.objects.create(title="Fall Dues", amount=100, due_date=timezone.now().date(), assigned_to=self.member)
        response = self.client.get(
            reverse("admin:dashboard_due_changelist"), {"is_paid__exact": "0", "is_template__exact": "0"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fall Dues")

    def test_due_change_view_renders(self):
        due = Due.objects.create(title="Fall Dues", amount=100, due_date=timezone.now().date(), assigned_to=self.member)
        response = self.client.get(reverse("admin:dashboard_due_change", args=[due.pk]))
        self.assertEqual(response.status_code, 200)

    def test_task_changelist_renders_and_filters(self):
        Task.objects.create(
            assigned_to=self.member,
            assigned_by=self.superuser,
            title="Clean the house",
            description="Weekly chore",
            due_date=timezone.now(),
        )
        response = self.client.get(
            reverse("admin:dashboard_task_changelist"),
            {"completed__exact": "0", "assigned_to__id__exact": self.member.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clean the house")

    def test_task_change_view_renders(self):
        task = Task.objects.create(
            assigned_to=self.member,
            assigned_by=self.superuser,
            title="Clean the house",
            description="Weekly chore",
            due_date=timezone.now(),
        )
        response = self.client.get(reverse("admin:dashboard_task_change", args=[task.pk]))
        self.assertEqual(response.status_code, 200)

    def test_announcement_changelist_renders_and_filters(self):
        Announcement.objects.create(
            chapter=self.chapter, author=self.superuser, title="Chapter Meeting", content="Meet at 7pm"
        )
        response = self.client.get(
            reverse("admin:dashboard_announcement_changelist"), {"chapter__id__exact": self.chapter.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Chapter Meeting")

    def test_announcement_change_view_renders(self):
        announcement = Announcement.objects.create(
            chapter=self.chapter, author=self.superuser, title="Chapter Meeting", content="Meet at 7pm"
        )
        response = self.client.get(reverse("admin:dashboard_announcement_change", args=[announcement.pk]))
        self.assertEqual(response.status_code, 200)
