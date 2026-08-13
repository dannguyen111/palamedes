from datetime import date, datetime, timezone as dt_timezone

from django.test import TestCase
from django.utils import timezone

from dashboard.models import Announcement, Due, HousePoint, Task
from palamedes.test_helpers import make_chapter_with_positions, make_user


class HousePointModelTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.recipient = make_user(chapter=self.chapter, status="NM")
        self.submitter = make_user(chapter=self.chapter, status="ACT")

    def make_point(self, **overrides):
        data = dict(
            user=self.recipient,
            chapter=self.chapter,
            submitted_by=self.submitter,
            amount=10,
            description="Attended chapter meeting",
        )
        data.update(overrides)
        return HousePoint.objects.create(**data)

    def test_str_includes_username_amount_and_status_display(self):
        point = self.make_point()
        self.assertEqual(
            str(point), f"{self.recipient.username} - 10 - Pending Approval"
        )

    def test_status_defaults_to_pending(self):
        point = self.make_point()
        self.assertEqual(point.status, "PENDING")

    def test_date_for_defaults_to_today(self):
        # default=timezone.now (a datetime-returning callable) on a
        # DateField: the in-memory attribute holds the raw datetime until it
        # round-trips through the DB, where DateField.to_python truncates it
        # to a date on the way in. Reload to see the coerced value. Compare
        # against timezone.now().date() rather than date.today() — settings
        # pin TIME_ZONE='UTC', which can differ from local system time.
        point = self.make_point()
        point.refresh_from_db()
        self.assertEqual(point.date_for, timezone.now().date())

    def test_amount_can_be_negative_for_penalties(self):
        point = self.make_point(amount=-5)
        self.assertEqual(point.amount, -5)

    def test_assigned_approver_optional(self):
        point = self.make_point()
        self.assertIsNone(point.assigned_approver)

    def test_assigned_approver_set_null_when_approver_deleted(self):
        approver = make_user(chapter=self.chapter, status="ACT")
        point = self.make_point(assigned_approver=approver)
        approver.delete()
        point.refresh_from_db()
        self.assertIsNone(point.assigned_approver)


class DueModelTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter)

    def test_str_includes_title_and_amount(self):
        due = Due.objects.create(
            title="Fall 2025 Dues", amount="150.00", due_date=date.today(),
            assigned_to=self.user,
        )
        self.assertEqual(str(due), "Fall 2025 Dues - $150.00")

    def test_is_paid_and_is_template_default_to_false(self):
        due = Due.objects.create(
            title="Fall 2025 Dues", amount="150.00", due_date=date.today(),
            assigned_to=self.user,
        )
        self.assertFalse(due.is_paid)
        self.assertFalse(due.is_template)

    def test_assigned_to_optional_for_template_dues(self):
        due = Due.objects.create(
            title="Fall 2025 Dues", amount="150.00", due_date=date.today(),
            is_template=True,
        )
        self.assertIsNone(due.assigned_to)

    def test_due_deleted_when_assigned_user_deleted(self):
        due = Due.objects.create(
            title="Fall 2025 Dues", amount="150.00", due_date=date.today(),
            assigned_to=self.user,
        )
        self.user.delete()
        self.assertFalse(Due.objects.filter(pk=due.pk).exists())


class TaskModelTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.assignee = make_user(chapter=self.chapter)
        self.assigner = make_user(chapter=self.chapter, status="ACT")

    def test_str_returns_title(self):
        task = Task.objects.create(
            assigned_to=self.assignee,
            assigned_by=self.assigner,
            title="Clean the house",
            description="Weekly chore",
            due_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        )
        self.assertEqual(str(task), "Clean the house")

    def test_completed_defaults_to_false(self):
        task = Task.objects.create(
            assigned_to=self.assignee,
            assigned_by=self.assigner,
            title="Clean the house",
            description="Weekly chore",
            due_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        )
        self.assertFalse(task.completed)

    def test_assigned_by_set_null_when_assigner_deleted(self):
        task = Task.objects.create(
            assigned_to=self.assignee,
            assigned_by=self.assigner,
            title="Clean the house",
            description="Weekly chore",
            due_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        )
        self.assigner.delete()
        task.refresh_from_db()
        self.assertIsNone(task.assigned_by)

    def test_task_deleted_when_assignee_deleted(self):
        task = Task.objects.create(
            assigned_to=self.assignee,
            assigned_by=self.assigner,
            title="Clean the house",
            description="Weekly chore",
            due_date=datetime(2026, 1, 1, tzinfo=dt_timezone.utc),
        )
        self.assignee.delete()
        self.assertFalse(Task.objects.filter(pk=task.pk).exists())


class AnnouncementModelTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.author = make_user(chapter=self.chapter, status="ACT")

    def test_str_includes_title_and_chapter_name(self):
        announcement = Announcement.objects.create(
            chapter=self.chapter,
            author=self.author,
            title="Chapter Meeting",
            content="Mandatory attendance.",
        )
        self.assertEqual(str(announcement), "Chapter Meeting - Theta Chi")

    def test_date_posted_auto_populates(self):
        announcement = Announcement.objects.create(
            chapter=self.chapter,
            author=self.author,
            title="Chapter Meeting",
            content="Mandatory attendance.",
        )
        self.assertIsNotNone(announcement.date_posted)

    def test_announcement_deleted_when_chapter_deleted(self):
        announcement = Announcement.objects.create(
            chapter=self.chapter,
            author=self.author,
            title="Chapter Meeting",
            content="Mandatory attendance.",
        )
        self.chapter.delete()
        self.assertFalse(Announcement.objects.filter(pk=announcement.pk).exists())
