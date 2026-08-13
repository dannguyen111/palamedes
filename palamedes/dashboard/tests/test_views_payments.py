from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Due
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
        self.due = Due.objects.create(
            title="Fall Dues", amount="100.00", due_date=date.today(),
            assigned_to=self.owner, is_paid=False,
        )

    def test_anonymous_user_is_redirected_to_login(self):
        url = reverse("make_mark_paid", kwargs={"pk": self.due.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_nonexistent_pk_returns_404(self):
        self.owner_login()
        response = self.client.get(reverse("make_mark_paid", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def owner_login(self):
        self.client.force_login(self.owner)

    def test_any_logged_in_user_can_view_any_due_no_permission_gate(self):
        # No permission check at all here — unlike mark_paid (which at
        # least checks can_manage_finance, even if unguarded against
        # position=None). Any authenticated user, including one from a
        # completely different chapter with no relation to this due, can
        # view it. Pinning the gap; see codebase-notes.md §6.
        other_chapter, _ = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM005", active_invite_code="OTHACT05"
        )
        stranger = make_user(chapter=other_chapter)
        self.client.force_login(stranger)
        response = self.client.get(reverse("make_mark_paid", kwargs={"pk": self.due.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["due"], self.due)


class DuesMemberViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.member = make_user(chapter=self.chapter)

    def test_anonymous_user_can_view_without_logging_in(self):
        # dues_member (URL name brothers_due) is the one dashboard view with
        # no @login_required — anonymous access is currently possible.
        # Pinning the gap; see codebase-notes.md §6.
        response = self.client.get(
            reverse("brothers_due", kwargs={"pk": self.member.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/member_dues_details.html")

    def test_cross_chapter_user_can_view_with_no_scoping(self):
        other_chapter, _ = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM006", active_invite_code="OTHACT06"
        )
        outsider = make_user(chapter=other_chapter)
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("brothers_due", kwargs={"pk": self.member.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["brother"], self.member)

    def test_nonexistent_pk_returns_404(self):
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

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_bulk_payment_marks_owned_dues_paid_and_zeroed(self, mock_retrieve):
        due2 = Due.objects.create(
            title="Spring Dues", amount="50.00", due_date=date.today(),
            assigned_to=self.user, is_paid=False,
        )
        mock_retrieve.return_value = MagicMock(
            metadata={
                "payment_type": "bulk_payment",
                "due_ids_str": f"{self.due.pk},{due2.pk}",
            }
        )
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_bulk"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/successful_payment.html")
        self.due.refresh_from_db()
        due2.refresh_from_db()
        self.assertTrue(self.due.is_paid)
        self.assertEqual(self.due.amount, 0)
        self.assertTrue(due2.is_paid)
        self.assertEqual(due2.amount, 0)

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_bulk_payment_only_affects_dues_owned_by_requesting_user(self, mock_retrieve):
        other_user = make_user(chapter=self.chapter)
        others_due = Due.objects.create(
            title="Not Yours", amount="20.00", due_date=date.today(),
            assigned_to=other_user, is_paid=False,
        )
        mock_retrieve.return_value = MagicMock(
            metadata={
                "payment_type": "bulk_payment",
                "due_ids_str": f"{self.due.pk},{others_due.pk}",
            }
        )
        self.client.get(reverse("payment_success"), {"session_id": "sess_bulk2"})
        others_due.refresh_from_db()
        self.assertFalse(others_due.is_paid)
        self.assertEqual(others_due.amount, Decimal("20.00"))

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_single_payment_full_amount_marks_due_paid(self, mock_retrieve):
        mock_retrieve.return_value = MagicMock(
            metadata={"payment_type": "single", "due_id": str(self.due.pk)},
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
        mock_retrieve.return_value = MagicMock(
            metadata={"payment_type": "single", "due_id": str(self.due.pk)},
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
        mock_retrieve.return_value = MagicMock(
            metadata={"payment_type": "single", "due_id": str(self.due.pk)},
            amount_total=4000,
        )
        self.client.get(reverse("payment_success"), {"session_id": "sess_replay"})
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, Decimal("60.00"))

        # Second hit with the same session_id should be a no-op (idempotency
        # guard via request.session['processed_sessions']).
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_replay"}
        )
        self.assertEqual(response.status_code, 200)
        self.due.refresh_from_db()
        self.assertEqual(self.due.amount, Decimal("60.00"))

    @patch("dashboard.views.stripe.checkout.Session.retrieve")
    def test_single_payment_has_no_ownership_check_on_the_due(self, mock_retrieve):
        # get_object_or_404(Due, pk=due_id) here has no assigned_to filter,
        # unlike payment_page/process_payment which both scope by
        # assigned_to=request.user. Any logged-in user who obtains/guesses a
        # valid session_id referencing someone else's due can mark it paid
        # through this view. Pinning the gap; see codebase-notes.md §6.
        other_user = make_user(chapter=self.chapter)
        others_due = Due.objects.create(
            title="Not Yours", amount="100.00", due_date=date.today(),
            assigned_to=other_user, is_paid=False,
        )
        mock_retrieve.return_value = MagicMock(
            metadata={"payment_type": "single", "due_id": str(others_due.pk)},
            amount_total=10000,
        )
        # self.user (not others_due's owner) hits payment_success.
        response = self.client.get(
            reverse("payment_success"), {"session_id": "sess_cross_user"}
        )
        self.assertEqual(response.status_code, 200)
        others_due.refresh_from_db()
        self.assertTrue(others_due.is_paid)
