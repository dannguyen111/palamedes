from datetime import date

from django.test import TestCase

from dashboard.forms import (
    ActivePointRequestForm,
    BulkDueForm,
    BulkPointForm,
    DateInput,
    DirectPointAssignmentForm,
    NMPointRequestForm,
    SingleDueForm,
)
from palamedes.test_helpers import make_chapter_with_positions, make_user


class DateInputWidgetTests(TestCase):
    def test_input_type_is_date(self):
        self.assertEqual(DateInput().input_type, "date")


class NMPointRequestFormTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.nm_user = make_user(chapter=self.chapter, status="NM")
        self.same_chapter_active = make_user(chapter=self.chapter, status="ACT")
        self.same_chapter_nm = make_user(chapter=self.chapter, status="NM")
        self.other_chapter, _ = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM001", active_invite_code="OTHACT01"
        )
        self.other_chapter_active = make_user(chapter=self.other_chapter, status="ACT")

    def test_approver_queryset_limited_to_actives_in_same_chapter(self):
        form = NMPointRequestForm(self.nm_user)
        queryset = form.fields["assigned_approver"].queryset
        self.assertIn(self.same_chapter_active, queryset)
        self.assertNotIn(self.same_chapter_nm, queryset)
        self.assertNotIn(self.other_chapter_active, queryset)

    def test_approver_field_relabeled_and_required(self):
        form = NMPointRequestForm(self.nm_user)
        self.assertEqual(
            form.fields["assigned_approver"].label, "Request Approval From"
        )
        self.assertTrue(form.fields["assigned_approver"].required)

    def test_valid_data_with_eligible_approver_is_valid(self):
        form = NMPointRequestForm(
            self.nm_user,
            data={
                "amount": 5,
                "description": "Attended event",
                "date_for": date.today(),
                "assigned_approver": self.same_chapter_active.pk,
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_approver_is_invalid(self):
        form = NMPointRequestForm(
            self.nm_user,
            data={
                "amount": 5,
                "description": "Attended event",
                "date_for": date.today(),
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("assigned_approver", form.errors)


class ActivePointRequestFormTests(TestCase):
    def test_valid_data_is_valid(self):
        form = ActivePointRequestForm(
            data={"amount": 5, "description": "Attended event", "date_for": date.today()}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_missing_amount_is_invalid(self):
        form = ActivePointRequestForm(
            data={"description": "Attended event", "date_for": date.today()}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)

    def test_has_no_assigned_approver_field(self):
        form = ActivePointRequestForm()
        self.assertNotIn("assigned_approver", form.fields)


class DirectPointAssignmentFormTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.nm_member = make_user(chapter=self.chapter, status="NM")
        self.active_member = make_user(chapter=self.chapter, status="ACT")

    def test_can_manage_points_sees_whole_chapter(self):
        manager = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["President"]
        )
        form = DirectPointAssignmentForm(manager)
        queryset = form.fields["user"].queryset
        self.assertIn(self.nm_member, queryset)
        self.assertIn(self.active_member, queryset)
        self.assertEqual(form.fields["user"].label, "Assign to Member")

    def test_without_can_manage_points_sees_only_new_members(self):
        limited_user = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        form = DirectPointAssignmentForm(limited_user)
        queryset = form.fields["user"].queryset
        self.assertIn(self.nm_member, queryset)
        self.assertNotIn(self.active_member, queryset)
        self.assertEqual(form.fields["user"].label, "Assign to New Member")

    def test_user_with_no_position_does_not_crash_and_sees_only_new_members(self):
        # position=None: __init__ uses getattr(request_user, 'position', None)
        # defensively, unlike several dashboard views that access
        # request.user.position.<flag> unguarded — see codebase-notes.md §6.
        positionless_user = make_user(chapter=self.chapter, status="ACT", position=None)
        form = DirectPointAssignmentForm(positionless_user)
        queryset = form.fields["user"].queryset
        self.assertIn(self.nm_member, queryset)
        self.assertNotIn(self.active_member, queryset)


class SingleDueFormTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.member = make_user(chapter=self.chapter)
        self.requester = make_user(chapter=self.chapter, status="ACT")

    def valid_data(self, **overrides):
        data = {
            "title": "Fall Dues",
            "amount": 100,
            "due_date": date.today(),
            "assigned_to": self.member.pk,
            "type": "CHARGE",
        }
        data.update(overrides)
        return data

    def test_charge_type_forces_amount_positive(self):
        form = SingleDueForm(self.requester, data=self.valid_data(amount=-50, type="CHARGE"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], 50)

    def test_aid_type_forces_amount_negative(self):
        form = SingleDueForm(self.requester, data=self.valid_data(amount=50, type="AID"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], -50)

    def test_assigned_to_queryset_limited_to_requesters_chapter(self):
        other_chapter, _ = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM002", active_invite_code="OTHACT02"
        )
        outsider = make_user(chapter=other_chapter)
        form = SingleDueForm(self.requester)
        queryset = form.fields["assigned_to"].queryset
        self.assertIn(self.member, queryset)
        self.assertNotIn(outsider, queryset)


class BulkDueFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "title": "Fall Dues",
            "amount": "100.00",
            "due_date": date.today(),
            "target_group": "ALL",
        }
        data.update(overrides)
        return data

    def test_valid_data_is_valid(self):
        form = BulkDueForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_pledge_class_without_semester_or_year_is_still_valid(self):
        # No clean() override enforces pledge_semester/pledge_year when
        # target_group=PLEDGE_CLASS is chosen — the form itself doesn't
        # catch this, only ad hoc handling in the view. Pinning that the
        # form alone considers this valid — see codebase-notes.md §5.
        form = BulkDueForm(data=self.valid_data(target_group="PLEDGE_CLASS"))
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_target_group_choice_is_rejected(self):
        form = BulkDueForm(data=self.valid_data(target_group="NOT_A_CHOICE"))
        self.assertFalse(form.is_valid())
        self.assertIn("target_group", form.errors)

    def test_selected_user_ids_not_required(self):
        form = BulkDueForm(data=self.valid_data())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["selected_user_ids"], "")


class BulkPointFormTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            "type": "AWARD",
            "amount": 5,
            "description": "Chapter event",
            "date_for": date.today(),
            "target_group": "ALL",
        }
        data.update(overrides)
        return data

    def test_award_type_forces_amount_positive(self):
        form = BulkPointForm(data=self.valid_data(amount=5, type="AWARD"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], 5)

    def test_penalty_type_forces_amount_negative(self):
        form = BulkPointForm(data=self.valid_data(amount=5, type="PENALTY"))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["amount"], -5)

    def test_amount_must_be_at_least_one(self):
        form = BulkPointForm(data=self.valid_data(amount=0))
        self.assertFalse(form.is_valid())
        self.assertIn("amount", form.errors)
