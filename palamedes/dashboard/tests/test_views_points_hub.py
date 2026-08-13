from django.test import TestCase
from django.urls import reverse

from dashboard.models import HousePoint
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user


@PLAIN_STATIC_STORAGE
class PointsHubViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("points_hub"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('points_hub')}"
        )

    def test_total_points_sums_only_approved_points(self):
        HousePoint.objects.create(
            user=self.user, chapter=self.chapter, amount=15, description="a",
            status="APPROVED",
        )
        HousePoint.objects.create(
            user=self.user, chapter=self.chapter, amount=99, description="b",
            status="PENDING",
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("points_hub"))
        self.assertEqual(response.context["total_points"], 15)


class ActionItemsTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")
        self.other = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(self.user)

    def _get(self):
        return self.client.get(reverse("points_hub"))

    def test_includes_points_awaiting_my_approval(self):
        point = HousePoint.objects.create(
            user=self.other, chapter=self.chapter, submitted_by=self.other,
            assigned_approver=self.user, amount=5, description="x", status="PENDING",
        )
        response = self._get()
        self.assertIn(point, list(response.context["my_action_items"]))

    def test_includes_my_countered_submissions(self):
        point = HousePoint.objects.create(
            user=self.user, chapter=self.chapter, submitted_by=self.user,
            amount=5, description="x", status="COUNTERED",
        )
        response = self._get()
        self.assertIn(point, list(response.context["my_action_items"]))

    def test_excludes_unrelated_points(self):
        point = HousePoint.objects.create(
            user=self.other, chapter=self.chapter, submitted_by=self.other,
            amount=5, description="x", status="PENDING",
        )
        response = self._get()
        self.assertNotIn(point, list(response.context["my_action_items"]))


class ExecQueueTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.submitter = make_user(chapter=self.chapter, status="ACT")

    def test_empty_without_can_manage_points(self):
        limited = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        HousePoint.objects.create(
            user=self.submitter, chapter=self.chapter, submitted_by=self.submitter,
            amount=5, description="x", status="PENDING",
        )
        self.client.force_login(limited)
        response = self.client.get(reverse("points_hub"))
        self.assertEqual(list(response.context["exec_queue"]), [])

    def test_populated_with_can_manage_points_excluding_self_submitted(self):
        manager = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )
        other_pending = HousePoint.objects.create(
            user=self.submitter, chapter=self.chapter, submitted_by=self.submitter,
            amount=5, description="x", status="PENDING",
        )
        self_submitted = HousePoint.objects.create(
            user=manager, chapter=self.chapter, submitted_by=manager,
            amount=5, description="x", status="PENDING",
        )
        self.client.force_login(manager)
        response = self.client.get(reverse("points_hub"))
        queue = list(response.context["exec_queue"])
        self.assertIn(other_pending, queue)
        self.assertNotIn(self_submitted, queue)

    def test_empty_when_position_is_none(self):
        positionless = make_user(chapter=self.chapter, status="ACT", position=None)
        self.client.force_login(positionless)
        response = self.client.get(reverse("points_hub"))
        self.assertEqual(list(response.context["exec_queue"]), [])


class LeaderboardTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(self.user)

    def test_zero_point_members_are_included_via_coalesce(self):
        zero_point_active = make_user(chapter=self.chapter, status="ACT")
        response = self.client.get(reverse("points_hub"))
        active_board = {u.pk: u for u in response.context["active_leaderboard"]}
        self.assertIn(zero_point_active.pk, active_board)
        self.assertEqual(active_board[zero_point_active.pk].total_points_val, 0)

    def test_active_and_nm_split_correctly(self):
        active_member = make_user(chapter=self.chapter, status="ACT")
        nm_member = make_user(chapter=self.chapter, status="NM")
        response = self.client.get(reverse("points_hub"))
        active_ids = {u.pk for u in response.context["active_leaderboard"]}
        nm_ids = {u.pk for u in response.context["nm_leaderboard"]}
        self.assertIn(active_member.pk, active_ids)
        self.assertNotIn(active_member.pk, nm_ids)
        self.assertIn(nm_member.pk, nm_ids)
        self.assertNotIn(nm_member.pk, active_ids)

    def test_ordered_descending_by_total_points(self):
        low = make_user(chapter=self.chapter, status="ACT")
        high = make_user(chapter=self.chapter, status="ACT")
        HousePoint.objects.create(
            user=low, chapter=self.chapter, amount=5, description="x", status="APPROVED"
        )
        HousePoint.objects.create(
            user=high, chapter=self.chapter, amount=50, description="x", status="APPROVED"
        )
        response = self.client.get(reverse("points_hub"))
        active_board = list(response.context["active_leaderboard"])
        high_index = next(i for i, u in enumerate(active_board) if u.pk == high.pk)
        low_index = next(i for i, u in enumerate(active_board) if u.pk == low.pk)
        self.assertLess(high_index, low_index)


class MotherLogsTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")
        self.recipient = make_user(chapter=self.chapter, status="ACT")
        self.approver = make_user(chapter=self.chapter, status="ACT")
        self.point = HousePoint.objects.create(
            user=self.recipient, chapter=self.chapter, submitted_by=self.user,
            assigned_approver=self.approver, amount=5, description="x",
            status="APPROVED",
        )
        self.client.force_login(self.user)

    def test_recipient_filter_applies_when_digit(self):
        other_point = HousePoint.objects.create(
            user=self.user, chapter=self.chapter, submitted_by=self.user,
            amount=1, description="y", status="APPROVED",
        )
        response = self.client.get(
            reverse("points_hub"), {"recipient": str(self.recipient.pk)}
        )
        active_logs = list(response.context["active_logs"])
        self.assertIn(self.point, active_logs)
        self.assertNotIn(other_point, active_logs)
        self.assertEqual(response.context["current_recipient"], self.recipient.pk)

    def test_non_digit_recipient_is_ignored(self):
        response = self.client.get(reverse("points_hub"), {"recipient": "not-a-number"})
        self.assertIsNone(response.context["current_recipient"])
        active_logs = list(response.context["active_logs"])
        self.assertIn(self.point, active_logs)

    def test_approver_filter_applies_when_digit(self):
        response = self.client.get(
            reverse("points_hub"), {"approver": str(self.approver.pk)}
        )
        self.assertEqual(response.context["current_approver"], self.approver.pk)
        self.assertIn(self.point, list(response.context["active_logs"]))

    def test_invalid_sort_falls_back_to_default(self):
        response = self.client.get(reverse("points_hub"), {"sort": "'; DROP TABLE"})
        self.assertEqual(response.context["current_sort"], "'; DROP TABLE")
        # Falls back to -date_submitted ordering without raising.
        self.assertEqual(response.status_code, 200)

    def test_valid_sort_is_applied(self):
        cheap = HousePoint.objects.create(
            user=self.recipient, chapter=self.chapter, submitted_by=self.user,
            amount=1, description="cheap", status="APPROVED",
        )
        response = self.client.get(reverse("points_hub"), {"sort": "amount"})
        self.assertEqual(response.context["current_sort"], "amount")
        active_logs = list(response.context["active_logs"])
        cheap_index = next(i for i, p in enumerate(active_logs) if p.pk == cheap.pk)
        expensive_index = next(i for i, p in enumerate(active_logs) if p.pk == self.point.pk)
        self.assertLess(cheap_index, expensive_index)

    def test_nm_logs_and_active_logs_split_by_recipient_status(self):
        nm_recipient = make_user(chapter=self.chapter, status="NM")
        nm_point = HousePoint.objects.create(
            user=nm_recipient, chapter=self.chapter, submitted_by=self.user,
            amount=3, description="nm point", status="APPROVED",
        )
        response = self.client.get(reverse("points_hub"))
        self.assertIn(nm_point, list(response.context["nm_logs"]))
        self.assertNotIn(nm_point, list(response.context["active_logs"]))
        self.assertIn(self.point, list(response.context["active_logs"]))
        self.assertNotIn(self.point, list(response.context["nm_logs"]))

    def test_chapter_members_and_approvers_list(self):
        nm_member = make_user(chapter=self.chapter, status="NM")
        response = self.client.get(reverse("points_hub"))
        chapter_members = list(response.context["chapter_members"])
        approvers_list = list(response.context["approvers_list"])
        self.assertIn(self.recipient, chapter_members)
        self.assertIn(nm_member, chapter_members)
        self.assertNotIn(nm_member, approvers_list)
