from datetime import date

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Due
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user


@PLAIN_STATIC_STORAGE
class DuesDashboardViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("dues_dashboard"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('dues_dashboard')}"
        )

    def test_position_none_crashes(self):
        # is_treasurer = user.position.can_manage_finance is unguarded — see
        # codebase-notes.md §6.
        user = make_user(chapter=self.chapter, status="ACT", position=None)
        self.client.force_login(user)
        with self.assertRaises(AttributeError):
            self.client.get(reverse("dues_dashboard"))

    def test_is_treasurer_reflects_can_manage_finance(self):
        treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        self.client.force_login(treasurer)
        response = self.client.get(reverse("dues_dashboard"))
        self.assertTrue(response.context["is_treasurer"])

        non_treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        self.client.force_login(non_treasurer)
        response = self.client.get(reverse("dues_dashboard"))
        self.assertFalse(response.context["is_treasurer"])

    def test_my_dues_my_history_and_total_due(self):
        user = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        Due.objects.create(
            title="Unpaid", amount="40.00", due_date=date.today(),
            assigned_to=user, is_paid=False,
        )
        Due.objects.create(
            title="Paid", amount="60.00", due_date=date.today(),
            assigned_to=user, is_paid=True,
        )
        self.client.force_login(user)
        response = self.client.get(reverse("dues_dashboard"))
        self.assertEqual(len(response.context["my_dues"]), 1)
        self.assertEqual(len(response.context["my_history"]), 1)
        self.assertEqual(response.context["total_due"], 40)


@PLAIN_STATIC_STORAGE
class ManageDuesCreationViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )

    def test_no_permission_is_denied_not_crashed(self):
        # Guarded with `request.user.position and ...` — unlike
        # dues_dashboard/mark_paid, this view itself degrades gracefully.
        # (Not following the redirect: dues_dashboard is its own unguarded
        # `user.position.can_manage_finance` crash for this same positionless
        # user — see DuesDashboardViewTests.test_position_none_crashes. This
        # test only asserts manage_dues_creation's own behavior.)
        positionless = make_user(chapter=self.chapter, status="ACT", position=None)
        self.client.force_login(positionless)
        response = self.client.get(reverse("manage_dues_creation"))
        self.assertRedirects(
            response, reverse("dues_dashboard"), fetch_redirect_response=False
        )

    def test_get_renders_both_forms_on_single_tab_by_default(self):
        self.client.force_login(self.treasurer)
        response = self.client.get(reverse("manage_dues_creation"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "single")

    def test_valid_single_charge_creates_due_and_redirects(self):
        member = make_user(chapter=self.chapter)
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse("manage_dues_creation"),
            data={
                "submit_single": "1",
                "title": "Fall Dues",
                "amount": 100,
                "due_date": date.today(),
                "assigned_to": member.pk,
                "type": "CHARGE",
            },
        )
        self.assertRedirects(response, reverse("dues_dashboard"))
        due = Due.objects.get()
        self.assertEqual(due.assigned_to, member)
        self.assertEqual(due.amount, 100)

    def test_invalid_single_submission_rerenders_without_crashing(self):
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse("manage_dues_creation"),
            data={"submit_single": "1", "title": "", "type": "CHARGE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Due.objects.count(), 0)

    def test_directory_selection_prefills_bulk_form_and_switches_tab(self):
        member = make_user(chapter=self.chapter)
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse("manage_dues_creation"),
            data={
                "directory_selection": "1",
                "selected_members": [str(member.pk)],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "bulk")
        bulk_form = response.context["bulk_form"]
        self.assertEqual(bulk_form.initial["target_group"], "SELECTED")
        self.assertEqual(bulk_form.initial["selected_user_ids"], str(member.pk))

    def test_bulk_charge_all_creates_due_for_every_chapter_member(self):
        make_user(chapter=self.chapter)
        make_user(chapter=self.chapter)
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse("manage_dues_creation"),
            data={
                "submit_bulk": "1",
                "title": "Fall Dues",
                "amount": "50.00",
                "due_date": date.today(),
                "target_group": "ALL",
            },
        )
        self.assertRedirects(response, reverse("dues_dashboard"))
        # treasurer + 2 members = 3 chapter members total.
        self.assertEqual(Due.objects.count(), 3)

    def test_bulk_charge_actives_and_nms_target_groups(self):
        nm_member = make_user(chapter=self.chapter, status="NM")
        active_member = make_user(chapter=self.chapter, status="ACT")
        self.client.force_login(self.treasurer)

        response = self.client.post(
            reverse("manage_dues_creation"),
            data={
                "submit_bulk": "1", "title": "NM Dues", "amount": "10.00",
                "due_date": date.today(), "target_group": "NMS",
            },
        )
        self.assertRedirects(response, reverse("dues_dashboard"))
        nm_due = Due.objects.get(title="NM Dues")
        self.assertEqual(nm_due.assigned_to, nm_member)

        response = self.client.post(
            reverse("manage_dues_creation"),
            data={
                "submit_bulk": "1", "title": "Active Dues", "amount": "10.00",
                "due_date": date.today(), "target_group": "ACTIVES",
            },
        )
        self.assertRedirects(response, reverse("dues_dashboard"))
        active_assignees = set(
            Due.objects.filter(title="Active Dues").values_list("assigned_to", flat=True)
        )
        self.assertIn(active_member.pk, active_assignees)
        self.assertIn(self.treasurer.pk, active_assignees)
        self.assertNotIn(nm_member.pk, active_assignees)

    def test_bulk_charge_selected_creates_due_only_for_chosen_ids(self):
        chosen = make_user(chapter=self.chapter)
        not_chosen = make_user(chapter=self.chapter)
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse("manage_dues_creation"),
            data={
                "submit_bulk": "1",
                "title": "Fall Dues",
                "amount": "50.00",
                "due_date": date.today(),
                "target_group": "SELECTED",
                "selected_user_ids": str(chosen.pk),
            },
        )
        self.assertRedirects(response, reverse("dues_dashboard"))
        due = Due.objects.get()
        self.assertEqual(due.assigned_to, chosen)

    def test_bulk_charge_pledge_class_is_broken(self):
        # Known bug pinned, not fixed: members.get('pledge_semester') is
        # invalid QuerySet.get() usage and members.filer(...) is a typo for
        # .filter(...) — see codebase-notes.md §5/§6. This branch currently
        # raises rather than creating any dues.
        self.client.force_login(self.treasurer)
        with self.assertRaises(Exception):
            self.client.post(
                reverse("manage_dues_creation"),
                data={
                    "submit_bulk": "1",
                    "title": "Fall Dues",
                    "amount": "50.00",
                    "due_date": date.today(),
                    "target_group": "PLEDGE_CLASS",
                    "pledge_semester": "Fall",
                    "pledge_year": 2025,
                },
            )
        self.assertEqual(Due.objects.count(), 0)

    def test_invalid_bulk_submission_rerenders_without_crashing(self):
        self.client.force_login(self.treasurer)
        response = self.client.post(
            reverse("manage_dues_creation"),
            data={"submit_bulk": "1", "target_group": "NOT_A_CHOICE"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Due.objects.count(), 0)


@PLAIN_STATIC_STORAGE
class MarkPaidViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.member = make_user(chapter=self.chapter)
        self.due = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.member, is_paid=False,
        )
        self.brothers_due_url = reverse(
            "brothers_due", kwargs={"pk": self.member.pk}
        )

    def test_position_none_crashes(self):
        # request.user.position.can_manage_finance is unguarded — see
        # codebase-notes.md §6.
        treasurer_without_position = make_user(
            chapter=self.chapter, status="ACT", position=None
        )
        self.client.force_login(treasurer_without_position)
        with self.assertRaises(AttributeError):
            self.client.post(
                reverse("mark_paid", kwargs={"pk": self.due.pk}), data={}
            )

    def test_without_permission_makes_no_change(self):
        no_permission = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["No Position"]
        )
        self.client.force_login(no_permission)
        response = self.client.post(
            reverse("mark_paid", kwargs={"pk": self.due.pk}), data={}
        )
        self.assertRedirects(response, self.brothers_due_url)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, 100)
        self.assertFalse(self.due.is_paid)

    def test_missing_amount_pays_due_in_full(self):
        treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        self.client.force_login(treasurer)
        response = self.client.post(
            reverse("mark_paid", kwargs={"pk": self.due.pk}), data={}
        )
        self.assertRedirects(response, self.brothers_due_url)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, 0)
        self.assertTrue(self.due.is_paid)

    def test_partial_payment_leaves_due_unpaid_with_remaining_balance(self):
        treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        self.client.force_login(treasurer)
        response = self.client.post(
            reverse("mark_paid", kwargs={"pk": self.due.pk}), data={"amount": "40"}
        )
        self.assertRedirects(response, self.brothers_due_url)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, 60)
        self.assertFalse(self.due.is_paid)

    def test_non_numeric_amount_is_rejected(self):
        treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        self.client.force_login(treasurer)
        response = self.client.post(
            reverse("mark_paid", kwargs={"pk": self.due.pk}), data={"amount": "abc"}
        )
        self.assertRedirects(response, self.brothers_due_url)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, 100)

    def test_negative_amount_is_rejected(self):
        treasurer = make_user(
            chapter=self.chapter, status="ACT", position=self.positions["Treasurer"]
        )
        self.client.force_login(treasurer)
        response = self.client.post(
            reverse("mark_paid", kwargs={"pk": self.due.pk}), data={"amount": "-5"}
        )
        self.assertRedirects(response, self.brothers_due_url)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, 100)
