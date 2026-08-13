from datetime import date, datetime, timedelta, timezone as dt_timezone

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Announcement, Due, HousePoint, Task
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user


@PLAIN_STATIC_STORAGE
class DashboardViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('dashboard')}"
        )

    def test_renders_dashboard_template(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/dashboard.html")

    def test_total_points_sums_only_approved_points(self):
        HousePoint.objects.create(
            user=self.user, chapter=self.chapter, amount=10, description="a",
            status="APPROVED",
        )
        HousePoint.objects.create(
            user=self.user, chapter=self.chapter, amount=100, description="b",
            status="PENDING",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["total_points"], 10)

    def test_pending_points_are_not_exposed_in_context(self):
        # pending_points is computed in the view but never added to the
        # context dict — dead code. Pinning that it stays absent, per
        # codebase-notes.md §5.
        HousePoint.objects.create(
            user=self.user, chapter=self.chapter, amount=100, description="b",
            status="PENDING",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertNotIn("pending_points", response.context)

    def test_dues_balance_sums_unpaid_dues_only(self):
        Due.objects.create(
            title="Fall Dues", amount="50.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )
        Due.objects.create(
            title="Spring Dues", amount="75.00", due_date=date.today(),
            assigned_to=self.user, is_paid=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["dues_balance"], 50)

    def test_pending_tasks_count_excludes_completed(self):
        Task.objects.create(
            assigned_to=self.user, title="Do a thing", description="x",
            due_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc), completed=False,
        )
        Task.objects.create(
            assigned_to=self.user, title="Already done", description="x",
            due_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc), completed=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.context["pending_tasks_count"], 1)

    def test_announcements_limited_to_five_most_recent_for_chapter(self):
        base = datetime.now(dt_timezone.utc)
        for i in range(7):
            a = Announcement.objects.create(
                chapter=self.chapter, author=self.user, title=f"Announcement {i}",
                content="x",
            )
            a.date_posted = base + timedelta(minutes=i)
            a.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        announcements = list(response.context["announcements"])
        self.assertEqual(len(announcements), 5)
        self.assertEqual(announcements[0].title, "Announcement 6")

    def test_user_without_chapter_gets_empty_announcements(self):
        chapterless_user = make_user(chapter=None)
        self.client.force_login(chapterless_user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(list(response.context["announcements"]), [])
