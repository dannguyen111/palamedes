from datetime import date

from django.test import TestCase
from django.urls import reverse

from dashboard.models import HousePoint
from users.models import Position
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user


@PLAIN_STATIC_STORAGE
class SubmitPointsViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.approver = make_user(chapter=self.chapter, status="ACT")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("submit_points"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('submit_points')}"
        )

    def test_nm_user_gets_approver_field_on_get(self):
        nm_user = make_user(chapter=self.chapter, status="NM")
        self.client.force_login(nm_user)
        response = self.client.get(reverse("submit_points"))
        self.assertIn("assigned_approver", response.context["form"].fields)

    def test_active_user_gets_no_approver_field_on_get(self):
        active_user = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(active_user)
        response = self.client.get(reverse("submit_points"))
        self.assertNotIn("assigned_approver", response.context["form"].fields)

    def test_nm_valid_post_creates_point_with_chosen_approver(self):
        nm_user = make_user(chapter=self.chapter, status="NM")
        self.client.force_login(nm_user)
        response = self.client.post(
            reverse("submit_points"),
            data={
                "amount": 5,
                "description": "Attended event",
                "date_for": date.today(),
                "assigned_approver": self.approver.pk,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        point = HousePoint.objects.get()
        self.assertEqual(point.user, nm_user)
        self.assertEqual(point.submitted_by, nm_user)
        self.assertEqual(point.chapter, self.chapter)
        self.assertEqual(point.assigned_approver, self.approver)
        self.assertEqual(point.status, "PENDING")

    def test_active_valid_post_creates_point_with_no_approver(self):
        active_user = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(active_user)
        response = self.client.post(
            reverse("submit_points"),
            data={"amount": 5, "description": "Attended event", "date_for": date.today()},
        )
        self.assertRedirects(response, reverse("dashboard"))
        point = HousePoint.objects.get()
        self.assertIsNone(point.assigned_approver)

    def test_nm_invalid_post_missing_approver_rerenders_with_errors(self):
        nm_user = make_user(chapter=self.chapter, status="NM")
        self.client.force_login(nm_user)
        response = self.client.post(
            reverse("submit_points"),
            data={"amount": 5, "description": "Attended event", "date_for": date.today()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(HousePoint.objects.count(), 0)


@PLAIN_STATIC_STORAGE
class AssignPointsViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.nm_target = make_user(chapter=self.chapter, status="NM")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("assign_points"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('assign_points')}"
        )

    def test_active_user_always_permitted_even_without_position(self):
        active_user = make_user(chapter=self.chapter, status="ACT", position=None)
        self.client.force_login(active_user)
        response = self.client.get(reverse("assign_points"))
        self.assertEqual(response.status_code, 200)

    def test_nm_without_can_manage_points_is_denied(self):
        nm_user = make_user(
            chapter=self.chapter, status="NM", position=self.positions["No Position"]
        )
        self.client.force_login(nm_user)
        response = self.client.get(reverse("assign_points"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_nm_with_can_manage_points_is_permitted(self):
        nm_manager = make_user(
            chapter=self.chapter, status="NM", position=self.positions["President"]
        )
        self.client.force_login(nm_manager)
        response = self.client.get(reverse("assign_points"))
        self.assertEqual(response.status_code, 200)

    def test_valid_post_auto_approves_and_assigns_points(self):
        active_user = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )
        self.client.force_login(active_user)
        response = self.client.post(
            reverse("assign_points"),
            data={
                "user": self.nm_target.pk,
                "amount": 5,
                "description": "Direct award",
                "date_for": date.today(),
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        point = HousePoint.objects.get()
        self.assertEqual(point.user, self.nm_target)
        self.assertEqual(point.submitted_by, active_user)
        self.assertEqual(point.assigned_approver, active_user)
        self.assertEqual(point.status, "APPROVED")


@PLAIN_STATIC_STORAGE
class ManagePointRequestViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        # is_top2 = request.user.position.can_manage_points ... is evaluated
        # unconditionally for the acting user on every request, unguarded —
        # so any acting user needs SOME Position row (even a no-permission
        # one) or the view raises AttributeError before permission logic
        # even runs. See test_position_none_crashes_regardless_of_other_permissions
        # below for that crash pinned deliberately; every other test here
        # needs a real position on whoever is POSTing.
        self.submitter = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        self.approver = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )

    def make_point(self, **overrides):
        data = dict(
            user=self.submitter,
            chapter=self.chapter,
            submitted_by=self.submitter,
            amount=10,
            description="x",
            status="PENDING",
        )
        data.update(overrides)
        return HousePoint.objects.create(**data)

    def test_unrelated_user_is_denied(self):
        point = self.make_point()
        stranger = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        self.client.force_login(stranger)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}), data={"action": "approve"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.status, "PENDING")

    def test_position_none_crashes_regardless_of_other_permissions(self):
        # is_top2 = request.user.position.can_manage_points ... is evaluated
        # unconditionally and unguarded, so ANY call by a position=None user
        # raises AttributeError before the is_approver/is_owner_countering
        # checks even matter — see codebase-notes.md §6.
        point = self.make_point(assigned_approver=None)
        approver_without_position = make_user(
            chapter=self.chapter, status="ACT", position=None
        )
        # Even though this user isn't the approver/submitter, the crash
        # happens before permission is even evaluated.
        self.client.force_login(approver_without_position)
        with self.assertRaises(AttributeError):
            self.client.post(
                reverse("manage_point", kwargs={"pk": point.pk}),
                data={"action": "approve"},
            )

    def test_assigned_approver_can_approve(self):
        point = self.make_point(assigned_approver=self.approver)
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}),
            data={"action": "approve", "feedback": "looks good"},
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.status, "APPROVED")
        self.assertEqual(point.feedback, "looks good")
        self.assertEqual(point.assigned_approver, self.approver)

    def test_approve_leaves_approver_unchanged_on_self_approval(self):
        point = self.make_point(submitted_by=self.submitter, assigned_approver=self.submitter)
        self.client.force_login(self.submitter)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}), data={"action": "approve"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.assigned_approver, self.submitter)

    def test_top2_can_approve_unassigned_request(self):
        point = self.make_point(assigned_approver=None)
        manager = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}), data={"action": "approve"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.status, "APPROVED")
        self.assertEqual(point.assigned_approver, manager)

    def test_reject_sets_status_and_approver(self):
        point = self.make_point(assigned_approver=self.approver)
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}),
            data={"action": "reject", "feedback": "not enough evidence"},
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.status, "REJECTED")
        self.assertEqual(point.feedback, "not enough evidence")
        self.assertEqual(point.assigned_approver, self.approver)

    def test_owner_can_counter_a_countered_request(self):
        point = self.make_point(
            status="COUNTERED", assigned_approver=self.approver, amount=10
        )
        self.client.force_login(self.submitter)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}),
            data={"action": "counter", "new_amount": "7"},
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.amount, 7)
        self.assertEqual(point.status, "PENDING")

    def test_approver_counter_on_pending_flips_to_countered(self):
        point = self.make_point(status="PENDING", assigned_approver=self.approver)
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}),
            data={"action": "counter", "new_amount": "3"},
        )
        point.refresh_from_db()
        self.assertEqual(point.status, "COUNTERED")
        self.assertEqual(point.assigned_approver, self.approver)
        self.assertEqual(point.amount, 3)

    def test_counter_with_non_numeric_amount_is_ignored(self):
        point = self.make_point(status="PENDING", assigned_approver=self.approver, amount=10)
        self.client.force_login(self.approver)
        response = self.client.post(
            reverse("manage_point", kwargs={"pk": point.pk}),
            data={"action": "counter", "new_amount": "not-a-number"},
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.amount, 10)
        self.assertEqual(point.status, "PENDING")

    def test_no_action_makes_no_changes(self):
        point = self.make_point(assigned_approver=self.approver)
        self.client.force_login(self.approver)
        response = self.client.post(reverse("manage_point", kwargs={"pk": point.pk}), data={})
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.status, "PENDING")


@PLAIN_STATIC_STORAGE
class EditLogPointViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.submitter = make_user(chapter=self.chapter, status="ACT")

    def make_point(self, target_status="ACT", **overrides):
        target = make_user(chapter=self.chapter, status=target_status)
        data = dict(
            user=target, chapter=self.chapter, submitted_by=self.submitter,
            amount=10, description="x", status="APPROVED",
        )
        data.update(overrides)
        return HousePoint.objects.create(**data)

    def test_no_permission_is_denied(self):
        point = self.make_point()
        limited = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        self.client.force_login(limited)
        response = self.client.post(
            reverse("edit_log_point", kwargs={"pk": point.pk}), data={"amount": "5"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.amount, 10)

    def test_can_manage_points_can_edit_any_point(self):
        point = self.make_point(target_status="ACT")
        manager = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("edit_log_point", kwargs={"pk": point.pk}), data={"amount": "20"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.amount, 20)

    def test_can_manage_nm_points_only_edits_nm_points(self):
        # None of the four standard positions isolate can_manage_nm_points
        # from can_manage_points (Vice President has both) — need a custom
        # position here to actually exercise the can_edit_nm-only branch.
        nm_only_position = Position.objects.create(
            chapter=self.chapter,
            title="NM Coordinator",
            can_manage_points=False,
            can_manage_nm_points=True,
        )
        nm_manager = make_user(
            chapter=self.chapter, status="ACT", position=nm_only_position
        )
        nm_point = self.make_point(target_status="NM")
        active_point = self.make_point(target_status="ACT")

        self.client.force_login(nm_manager)
        response = self.client.post(
            reverse("edit_log_point", kwargs={"pk": nm_point.pk}), data={"amount": "15"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        nm_point.refresh_from_db()
        self.assertEqual(nm_point.amount, 15)

        response = self.client.post(
            reverse("edit_log_point", kwargs={"pk": active_point.pk}), data={"amount": "15"}
        )
        active_point.refresh_from_db()
        self.assertEqual(active_point.amount, 10)  # unchanged, denied

    def test_invalid_amount_is_ignored(self):
        point = self.make_point()
        manager = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("edit_log_point", kwargs={"pk": point.pk}), data={"amount": "not-a-number"}
        )
        self.assertRedirects(response, reverse("points_hub"))
        point.refresh_from_db()
        self.assertEqual(point.amount, 10)


@PLAIN_STATIC_STORAGE
class ManagePointsCreationViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.manager = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )

    def test_no_permission_is_denied(self):
        limited = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        self.client.force_login(limited)
        response = self.client.get(reverse("manage_points_creation"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_position_none_is_denied_not_crashed(self):
        # Guarded with `request.user.position and ...`, unlike several other
        # views — confirms this one degrades gracefully.
        positionless = make_user(chapter=self.chapter, status="ACT", position=None)
        self.client.force_login(positionless)
        response = self.client.get(reverse("manage_points_creation"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_bulk_award_to_all_creates_approved_points_for_everyone(self):
        member_a = make_user(chapter=self.chapter, status="ACT")
        member_b = make_user(chapter=self.chapter, status="NM")
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("manage_points_creation"),
            data={
                "submit_bulk_points": "1",
                "type": "AWARD",
                "amount": 5,
                "description": "Chapter event",
                "date_for": date.today(),
                "target_group": "ALL",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        # manager + member_a + member_b = 3 chapter members total.
        self.assertEqual(HousePoint.objects.filter(status="APPROVED").count(), 3)
        for point in HousePoint.objects.all():
            self.assertEqual(point.assigned_approver, self.manager)

    def test_pledge_class_target_works_correctly(self):
        # Unlike the dues version, this PLEDGE_CLASS branch is implemented
        # correctly (base_qs.filter(...), no typo) — contrast case.
        matching = make_user(
            chapter=self.chapter, status="NM", pledge_semester="Fall", pledge_year=2025
        )
        non_matching = make_user(
            chapter=self.chapter, status="NM", pledge_semester="Spring", pledge_year=2025
        )
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("manage_points_creation"),
            data={
                "submit_bulk_points": "1",
                "type": "PENALTY",
                "amount": 5,
                "description": "Missed pledge event",
                "date_for": date.today(),
                "target_group": "PLEDGE_CLASS",
                "pledge_semester": "Fall",
                "pledge_year": 2025,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        points = HousePoint.objects.all()
        self.assertEqual(points.count(), 1)
        self.assertEqual(points.get().user, matching)
        self.assertEqual(points.get().amount, -5)

    def test_bulk_points_selected_target_group_only_awards_chosen_members(self):
        chosen = make_user(chapter=self.chapter, status="ACT")
        not_chosen = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("manage_points_creation"),
            data={
                "submit_bulk_points": "1",
                "type": "AWARD",
                "amount": 5,
                "description": "Selected only",
                "date_for": date.today(),
                "target_group": "SELECTED",
                "selected_user_ids": str(chosen.pk),
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        point = HousePoint.objects.get()
        self.assertEqual(point.user, chosen)

    def test_directory_selection_prefills_form(self):
        member = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("manage_points_creation"),
            data={
                "directory_selection": "1",
                "selected_members": [str(member.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["target_group"], "SELECTED")
        self.assertEqual(form.initial["selected_user_ids"], str(member.pk))

    def test_invalid_bulk_submission_does_not_create_points_or_crash(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("manage_points_creation"),
            data={
                "submit_bulk_points": "1",
                "type": "AWARD",
                "amount": 0,  # min_value=1, invalid
                "description": "Chapter event",
                "date_for": date.today(),
                "target_group": "ALL",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(HousePoint.objects.count(), 0)
