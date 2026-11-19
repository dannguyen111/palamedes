from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Due, ProcessedStripeSession
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user


@PLAIN_STATIC_STORAGE
class PaymentPageViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter)
        self.due = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("payment_page", kwargs={"pk": self.due.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_owner_can_view_payment_page(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("payment_page", kwargs={"pk": self.due.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/payment_page.html")
        self.assertEqual(response.context["due"], self.due)

    def test_non_owner_gets_404(self):
        other_user = make_user(chapter=self.chapter)
        self.client.force_login(other_user)
        response = self.client.get(reverse("payment_page", kwargs={"pk": self.due.pk}))
        self.assertEqual(response.status_code, 404)


class MakePaymentTreasurerViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.owner = make_user(chapter=self.chapter)
        self.treasurer = make_user(chapter=self.chapter, position=self.positions["Treasurer"])
        self.due = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.owner, is_paid=False,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("make_mark_paid", kwargs={"pk": self.due.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_nonexistent_pk_returns_404(self):
        self.client.force_login(self.treasurer)
        response = self.client.get(reverse("make_mark_paid", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_treasurer_can_view_due_in_own_chapter(self):
        self.client.force_login(self.treasurer)
        response = self.client.get(reverse("make_mark_paid", kwargs={"pk": self.due.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["due"], self.due)

    def test_member_without_finance_permission_is_denied(self):
        # Issue #52: this screen used to have no permission check.
        self.client.force_login(self.owner)
        response = self.client.get(reverse("make_mark_paid", kwargs={"pk": self.due.pk}))
        self.assertRedirects(response, reverse("dues_dashboard"))

    def test_treasurer_from_another_chapter_gets_404(self):
        other_chapter, other_positions = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM005", active_invite_code="OTHACT05"
        )
        outsider = make_user(chapter=other_chapter, position=other_positions["Treasurer"])
        self.client.force_login(outsider)
        response = self.client.get(reverse("make_mark_paid", kwargs={"pk": self.due.pk}))
        self.assertEqual(response.status_code, 404)


class DuesMemberViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.member = make_user(chapter=self.chapter)
        self.treasurer = make_user(chapter=self.chapter, position=self.positions["Treasurer"])

    def test_anonymous_user_is_redirected_to_login(self):
        # Issue #51: this page used to be readable without logging in.
        url = reverse("brothers_due", kwargs={"pk": self.member.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_member_without_finance_permission_is_denied(self):
        self.client.force_login(self.member)
        response = self.client.get(
            reverse("brothers_due", kwargs={"pk": self.member.pk})
        )
        self.assertRedirects(response, reverse("dues_dashboard"))

    def test_treasurer_from_another_chapter_gets_404(self):
        other_chapter, other_positions = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM006", active_invite_code="OTHACT06"
        )
        outsider = make_user(chapter=other_chapter, position=other_positions["Treasurer"])
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("brothers_due", kwargs={"pk": self.member.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_treasurer_can_view_member_in_own_chapter(self):
        self.client.force_login(self.treasurer)
        response = self.client.get(
            reverse("brothers_due", kwargs={"pk": self.member.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/member_dues_details.html")
        self.assertEqual(response.context["brother"], self.member)

    def test_nonexistent_pk_returns_404(self):
        self.client.force_login(self.treasurer)
        response = self.client.get(reverse("brothers_due", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_dues_ordered_unpaid_first_then_by_due_date(self):
        later_unpaid = Due.objects.create(
            title="Later", amount="10.00", due_date=date(2026, 6, 1),
            assigned_to=self.member, is_paid=False,
        )
        earlier_unpaid = Due.objects.create(
            title="Earlier", amount="10.00", due_date=date(2026, 1, 1),
            assigned_to=self.member, is_paid=False,
        )
        paid = Due.objects.create(
            title="Paid", amount="10.00", due_date=date(2025, 1, 1),
            assigned_to=self.member, is_paid=True,
        )
        self.client.force_login(self.treasurer)
        response = self.client.get(
            reverse("brothers_due", kwargs={"pk": self.member.pk})
        )
        dues = list(response.context["dues"])
        self.assertEqual(dues, [earlier_unpaid, later_unpaid, paid])


class CreateBulkCheckoutSessionViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter)
        self.due1 = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )
        self.due2 = Due.objects.create(
            title="Spring Dues", amount="50.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("create_bulk_checkout_session")
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_get_request_redirects_to_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("create_bulk_checkout_session"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_empty_post_body_is_treated_as_not_post_and_redirects_to_dashboard(self):
        # `if request.POST:` is a truthiness check on the QueryDict, not
        # `request.method == 'POST'` — an empty POST body is falsy and this
        # branch is skipped entirely, even though it genuinely was a POST
        # request. See codebase-notes.md §5.
        self.client.force_login(self.user)
        response = self.client.post(reverse("create_bulk_checkout_session"), data={})
        self.assertRedirects(response, reverse("dashboard"))

    @patch("dashboard.views.stripe.checkout.Session.create")
    def test_valid_post_creates_session_for_owned_dues_and_redirects(self, mock_create):
        mock_create.return_value = MagicMock(url="https://stripe.example/checkout/sess_123")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_bulk_checkout_session"),
            data={"due_ids": [str(self.due1.pk), str(self.due2.pk)]},
        )
        # The view calls redirect(url, code=303), but Django's redirect()
        # shortcut has no `code` kwarg (only `permanent`) — it's silently
        # ignored, so the actual response is a plain 302, not 303. Harmless
        # in practice (redirecting to Stripe's hosted checkout is a GET
        # either way), but the intent in the code doesn't match reality.
        self.assertRedirects(
            response, "https://stripe.example/checkout/sess_123", fetch_redirect_response=False
        )
        self.assertEqual(response.status_code, 302)
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        self.assertEqual(len(call_kwargs["line_items"]), 2)
        self.assertEqual(call_kwargs["metadata"]["payment_type"], "bulk_payment")
        due_ids_str = call_kwargs["metadata"]["due_ids_str"]
        self.assertEqual(
            set(due_ids_str.split(",")), {str(self.due1.pk), str(self.due2.pk)}
        )

    @patch("dashboard.views.stripe.checkout.Session.create")
    def test_other_users_due_ids_are_silently_excluded(self, mock_create):
        mock_create.return_value = MagicMock(url="https://stripe.example/checkout/sess_123")
        other_user = make_user(chapter=self.chapter)
        others_due = Due.objects.create(
            title="Not Yours", amount="20.00", due_date=date.today(),
            assigned_to=other_user, is_paid=False,
        )
        self.client.force_login(self.user)
        self.client.post(
            reverse("create_bulk_checkout_session"),
            data={"due_ids": [str(self.due1.pk), str(others_due.pk)]},
        )
        call_kwargs = mock_create.call_args.kwargs
        due_ids_str = call_kwargs["metadata"]["due_ids_str"]
        self.assertNotIn(str(others_due.pk), due_ids_str.split(","))

    @patch("dashboard.views.stripe.checkout.Session.create")
    def test_stripe_exception_returns_json_500(self, mock_create):
        mock_create.side_effect = Exception("stripe is down")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_bulk_checkout_session"),
            data={"due_ids": [str(self.due1.pk)]},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "stripe is down")


class ProcessPaymentViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter)
        self.due = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("create_checkout_session", kwargs={"pk": self.due.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_non_owner_gets_404(self):
        other_user = make_user(chapter=self.chapter)
        self.client.force_login(other_user)
        response = self.client.post(
            reverse("create_checkout_session", kwargs={"pk": self.due.pk}),
            data={"due_amount": "100"},
        )
        self.assertEqual(response.status_code, 404)

    def test_get_request_redirects_to_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("create_checkout_session", kwargs={"pk": self.due.pk})
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_missing_due_amount_raises_uncaught_exception(self):
        # amount = int(float(request.POST.get('due_amount')) * 100) sits
        # OUTSIDE the try/except that wraps the Stripe call, so a missing
        # or non-numeric due_amount crashes with an uncaught
        # TypeError/ValueError instead of the graceful JSON 500 the Stripe
        # call itself gets. See codebase-notes.md §5. Note the POST body
        # can't be completely empty here — `if request.POST:` is the same
        # truthiness check as create_bulk_checkout_session (see that test
        # class), so an empty body skips this branch and just redirects; a
        # non-empty body missing only the due_amount key is what reaches
        # the crash.
        self.client.force_login(self.user)
        with self.assertRaises(TypeError):
            self.client.post(
                reverse("create_checkout_session", kwargs={"pk": self.due.pk}),
                data={"unrelated_field": "x"},
            )

    def test_non_numeric_due_amount_raises_uncaught_exception(self):
        self.client.force_login(self.user)
        with self.assertRaises(ValueError):
            self.client.post(
                reverse("create_checkout_session", kwargs={"pk": self.due.pk}),
                data={"due_amount": "not-a-number"},
            )

    @patch("dashboard.views.stripe.checkout.Session.create")
    def test_valid_post_creates_session_and_redirects(self, mock_create):
        mock_create.return_value = MagicMock(url="https://stripe.example/checkout/sess_456")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_checkout_session", kwargs={"pk": self.due.pk}),
            data={"due_amount": "100"},
        )
        self.assertRedirects(
            response, "https://stripe.example/checkout/sess_456", fetch_redirect_response=False
        )
        call_kwargs = mock_create.call_args.kwargs
        self.assertEqual(call_kwargs["metadata"]["due_id"], self.due.pk)
        self.assertEqual(call_kwargs["metadata"]["payment_type"], "single")

    @patch("dashboard.views.stripe.checkout.Session.create")
    def test_stripe_exception_returns_json_500(self, mock_create):
        mock_create.side_effect = Exception("stripe is down")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("create_checkout_session", kwargs={"pk": self.due.pk}),
            data={"due_amount": "100"},
        )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"], "stripe is down")


class PaymentSuccessViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter)
        self.due = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )
        self.client.force_login(self.user)

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("payment_success")
        response = self.client.logout() or self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_missing_session_id_redirects_to_dashboard_with_error(self):
        response = self.client.get(reverse("payment_success"), follow=True)
        self.assertRedirects(response, reverse("dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("Missing payment session" in str(m) for m in messages))

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_stripe_retrieve_exception_redirects_to_dashboard_with_error(self, mock_retrieve):
        mock_retrieve.side_effect = Exception("stripe is down")
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_bad"}, follow=True
        )
        self.assertRedirects(response, reverse("dashboard"))
        messages = list(response.context["messages"])
        self.assertTrue(any("problem verifying your payment" in str(m) for m in messages))

    def paid_session(self, user=None, **metadata):
        """A mocked Stripe Checkout Session that Stripe reports as paid and
        that was started by `user` (self.user by default)."""
        amount_total = metadata.pop("amount_total", 10000)
        metadata.setdefault("user_id", str((user or self.user).id))
        return MagicMock(payment_status="paid", amount_total=amount_total, metadata=metadata)

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_bulk_payment_marks_owned_dues_paid_and_keeps_amounts(self, mock_retrieve):
        due2 = Due.objects.create(
            title="Spring Dues", amount="50.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )
        mock_retrieve.return_value = self.paid_session(
            payment_type="bulk_payment",
            due_ids_str=f"{self.due.pk},{due2.pk}",
            amount_total=15000,
        )
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_bulk"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/successful_payment.html")
        self.due.refresh_from_db()
        due2.refresh_from_db()
        self.assertTrue(self.due.is_paid)
        self.assertTrue(due2.is_paid)
        # Amounts are kept so payment history shows what was paid.
        self.assertEqual(self.due.amount, Decimal("100.00"))
        self.assertEqual(due2.amount, Decimal("50.00"))

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_bulk_payment_only_affects_dues_owned_by_requesting_user(self, mock_retrieve):
        other_user = make_user(chapter=self.chapter)
        others_due = Due.objects.create(
            title="Not Yours", amount="20.00", due_date=date.today(),
            assigned_to=other_user, is_paid=False,
        )
        mock_retrieve.return_value = self.paid_session(
            payment_type="bulk_payment",
            due_ids_str=f"{self.due.pk},{others_due.pk}",
        )
        self.client.get(reverse("payment_success"), {"session_id": "sess_bulk2"})
        others_due.refresh_from_db()
        self.assertFalse(others_due.is_paid)
        self.assertEqual(others_due.amount, Decimal("20.00"))

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_single_payment_full_amount_marks_due_paid(self, mock_retrieve):
        mock_retrieve.return_value = self.paid_session(
            payment_type="single", due_id=str(self.due.pk),
            amount_total=10000,  # $100.00 in cents
        )
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_full"}
        )
        self.assertEqual(response.status_code, 200)
        self.due.refresh_from_db()
        self.assertTrue(self.due.is_paid)
        self.assertEqual(self.due.amount, 0)

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_single_payment_partial_amount_leaves_remaining_balance(self, mock_retrieve):
        mock_retrieve.return_value = self.paid_session(
            payment_type="single", due_id=str(self.due.pk),
            amount_total=4000,  # $40.00 in cents
        )
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_partial"}
        )
        self.assertEqual(response.status_code, 200)
        self.due.refresh_from_db()
        self.assertFalse(self.due.is_paid)
        self.assertEqual(self.due.amount, Decimal("60.00"))

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_replayed_session_id_does_not_mutate_due_again(self, mock_retrieve):
        mock_retrieve.return_value = self.paid_session(
            payment_type="single", due_id=str(self.due.pk), amount_total=4000,
        )
        self.client.get(reverse("payment_success"), {"session_id": "sess_replay"})
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, Decimal("60.00"))

        # Logging out wipes the browser session. The replay guard lives in
        # the database, so a fresh login still can't apply it twice.
        self.client.logout()
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_replay"}
        )
        self.assertEqual(response.status_code, 200)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, Decimal("60.00"))
        self.assertEqual(ProcessedStripeSession.objects.filter(session_id="sess_replay").count(), 1)

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_replayed_bulk_session_is_recorded_once(self, mock_retrieve):
        mock_retrieve.return_value = self.paid_session(
            payment_type="bulk_payment", due_ids_str=str(self.due.pk),
        )
        self.client.get(reverse("payment_success"), {"session_id": "sess_bulk_replay"})
        self.client.get(reverse("payment_success"), {"session_id": "sess_bulk_replay"})
        self.assertEqual(
            ProcessedStripeSession.objects.filter(session_id="sess_bulk_replay").count(), 1
        )

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_unpaid_session_changes_nothing(self, mock_retrieve):
        # A session exists as soon as checkout starts, even if the member
        # cancels. Opening the success link for it must not mark anything paid.
        session = self.paid_session(
            payment_type="bulk_payment", due_ids_str=str(self.due.pk),
        )
        session.payment_status = "unpaid"
        mock_retrieve.return_value = session
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_abandoned"}, follow=True
        )
        self.assertRedirects(response, reverse("dues_dashboard"))
        self.due.refresh_from_db()
        self.assertFalse(self.due.is_paid)
        self.assertEqual(self.due.amount, Decimal("100.00"))
        self.assertFalse(ProcessedStripeSession.objects.exists())

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_session_started_by_another_user_changes_nothing(self, mock_retrieve):
        other_user = make_user(chapter=self.chapter)
        mock_retrieve.return_value = self.paid_session(
            user=other_user, payment_type="single", due_id=str(self.due.pk),
        )
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_not_mine"}, follow=True
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, Decimal("100.00"))
        self.assertFalse(ProcessedStripeSession.objects.exists())

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_single_payment_for_someone_elses_due_returns_404(self, mock_retrieve):
        # Issue #54: the Due lookup is now limited to the logged-in user.
        other_user = make_user(chapter=self.chapter)
        others_due = Due.objects.create(
            title="Not Yours", amount="100.00", due_date=date.today(),
            assigned_to=other_user, is_paid=False,
        )
        mock_retrieve.return_value = self.paid_session(
            payment_type="single", due_id=str(others_due.pk),
        )
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_cross_user"}
        )
        self.assertEqual(response.status_code, 404)
        others_due.refresh_from_db()
        self.assertFalse(others_due.is_paid)
        self.assertEqual(others_due.amount, Decimal("100.00"))
