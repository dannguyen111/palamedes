from datetime import date

from django.test import TestCase
from django.urls import reverse

from dashboard.models import Due
from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user


@PLAIN_STATIC_STORAGE
class DirectoryViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")
        self.other_chapter, _ = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM003", active_invite_code="OTHACT03"
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("brother_directory"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('brother_directory')}"
        )

    def test_lists_only_members_of_own_chapter(self):
        member = make_user(chapter=self.chapter, first_name="Alice", last_name="Smith")
        outsider = make_user(chapter=self.other_chapter, first_name="Bob", last_name="Jones")
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_directory"))
        members = list(response.context["members"])
        self.assertIn(member, members)
        self.assertNotIn(outsider, members)

    def test_query_filters_across_name_major_and_hometown(self):
        make_user(chapter=self.chapter, first_name="Alice", last_name="Zephyr", major="Biology")
        make_user(chapter=self.chapter, first_name="Bob", last_name="Smith", major="Chemistry")
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_directory"), {"q": "Biology"})
        members = list(response.context["members"])
        self.assertEqual(
            {m.first_name for m in members}, {"Alice"}
        )

    def test_status_filter_is_exact(self):
        make_user(chapter=self.chapter, status="NM", first_name="Newbie")
        make_user(chapter=self.chapter, status="ACT", first_name="Actual")
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_directory"), {"status": "NM"})
        members = list(response.context["members"])
        self.assertTrue(all(m.status == "NM" for m in members))
        self.assertIn("Newbie", [m.first_name for m in members])
        self.assertNotIn("Actual", [m.first_name for m in members])

    def test_search_query_defaults_to_empty_string(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_directory"))
        self.assertEqual(response.context["search_query"], "")


@PLAIN_STATIC_STORAGE
class UnpaidDirectoryViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("unpaid_directory"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('unpaid_directory')}"
        )

    def test_only_members_with_an_unpaid_due_are_listed(self):
        has_unpaid = make_user(chapter=self.chapter, first_name="Owes")
        Due.objects.create(
            title="Fall Dues", amount="50.00", due_date=date.today(),
            assigned_to=has_unpaid, is_paid=False,
        )
        all_paid = make_user(chapter=self.chapter, first_name="Clear")
        Due.objects.create(
            title="Fall Dues", amount="50.00", due_date=date.today(),
            assigned_to=all_paid, is_paid=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("unpaid_directory"))
        members = list(response.context["members"])
        self.assertIn(has_unpaid, members)
        self.assertNotIn(all_paid, members)

    def test_total_dues_annotation_sums_all_dues_not_just_unpaid(self):
        # ORM gotcha documented in codebase-notes.md §5: the base filter
        # (dues__is_paid=False) reuses its join for the Sum('dues__amount')
        # annotation, so a member with BOTH a paid and an unpaid due gets
        # total_dues = only the unpaid amount, not paid+unpaid combined —
        # pinning the actual (not assumed) behavior here.
        member = make_user(chapter=self.chapter, first_name="Mixed")
        Due.objects.create(
            title="Unpaid Due", amount="30.00", due_date=date.today(),
            assigned_to=member, is_paid=False,
        )
        Due.objects.create(
            title="Paid Due", amount="100.00", due_date=date.today(),
            assigned_to=member, is_paid=True,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("unpaid_directory"))
        members = {m.pk: m for m in response.context["members"]}
        self.assertEqual(members[member.pk].total_dues, 30)

    def test_filter_param_matches_name_major_hometown(self):
        member = make_user(chapter=self.chapter, first_name="Findme", major="Astrophysics")
        Due.objects.create(
            title="Fall Dues", amount="50.00", due_date=date.today(),
            assigned_to=member, is_paid=False,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("unpaid_directory"), {"filter": "Astro"})
        members = list(response.context["members"])
        self.assertIn(member, members)

    def test_status_filter_is_exact(self):
        nm = make_user(chapter=self.chapter, status="NM", first_name="Newbie")
        Due.objects.create(
            title="Fall Dues", amount="50.00", due_date=date.today(),
            assigned_to=nm, is_paid=False,
        )
        act = make_user(chapter=self.chapter, status="ACT", first_name="Actual")
        Due.objects.create(
            title="Fall Dues", amount="50.00", due_date=date.today(),
            assigned_to=act, is_paid=False,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse("unpaid_directory"), {"status": "NM"})
        members = list(response.context["members"])
        self.assertIn(nm, members)
        self.assertNotIn(act, members)

    def test_search_query_defaults_to_empty_string(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("unpaid_directory"))
        self.assertEqual(response.context["search_query"], "")


@PLAIN_STATIC_STORAGE
class BrotherProfileViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(chapter=self.chapter, status="ACT")
        self.other_chapter, _ = make_chapter_with_positions(
            name="Sigma Nu", nm_invite_code="OTHNM004", active_invite_code="OTHACT04"
        )

    def test_anonymous_user_is_redirected_to_login(self):
        brother = make_user(chapter=self.chapter)
        url = reverse("brother_profile", kwargs={"pk": brother.pk})
        response = self.client.get(url)
        self.assertRedirects(response, f"{reverse('login')}?next={url}")

    def test_nonexistent_pk_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_profile", kwargs={"pk": 999999}))
        self.assertEqual(response.status_code, 404)

    def test_same_chapter_profile_renders(self):
        brother = make_user(chapter=self.chapter, first_name="Sam")
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_profile", kwargs={"pk": brother.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "dashboard/brother_profile.html")
        self.assertEqual(response.context["brother"], brother)

    def test_cross_chapter_profile_is_denied(self):
        outsider = make_user(chapter=self.other_chapter, first_name="Outsider")
        self.client.force_login(self.user)
        response = self.client.get(reverse("brother_profile", kwargs={"pk": outsider.pk}))
        self.assertRedirects(response, reverse("dashboard"))
