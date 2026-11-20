from django.core import mail
from django.test import TestCase

from homepage.admin import approve_requests
from homepage.models import ChapterRequest
from users.models import Chapter, Position


class ApproveRequestsActionTests(TestCase):
    def make_request(self, **overrides):
        data = dict(
            fraternity_name="Theta Chi",
            university="UC Riverside",
            president_email="president@example.com",
        )
        data.update(overrides)
        return ChapterRequest.objects.create(**data)

    def test_marks_request_approved(self):
        req = self.make_request()
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        req.refresh_from_db()
        self.assertTrue(req.is_approved)

    def test_creates_chapter_matching_request(self):
        req = self.make_request()
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        chapter = Chapter.objects.get(name="Theta Chi", university="UC Riverside")
        self.assertIsNotNone(chapter.nm_invite_code)
        self.assertIsNotNone(chapter.active_invite_code)
        self.assertNotEqual(chapter.nm_invite_code, chapter.active_invite_code)

    def test_creates_four_positions_with_correct_flags(self):
        req = self.make_request()
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        chapter = Chapter.objects.get(name="Theta Chi", university="UC Riverside")
        positions = {p.title: p for p in chapter.positions.all()}

        self.assertEqual(
            set(positions.keys()),
            {"President", "Vice President", "Treasurer", "No Position"},
        )

        president = positions["President"]
        self.assertTrue(president.can_manage_roster)
        self.assertTrue(president.can_manage_finance)
        self.assertTrue(president.can_manage_points)
        self.assertTrue(president.can_manage_tasks)
        self.assertTrue(president.can_create_positions)
        self.assertTrue(president.can_manage_nm_points)

        vp = positions["Vice President"]
        self.assertTrue(vp.can_manage_roster)
        self.assertFalse(vp.can_manage_finance)
        self.assertTrue(vp.can_manage_points)
        self.assertTrue(vp.can_manage_tasks)
        self.assertFalse(vp.can_create_positions)
        self.assertTrue(vp.can_manage_nm_points)

        treasurer = positions["Treasurer"]
        self.assertFalse(treasurer.can_manage_roster)
        self.assertTrue(treasurer.can_manage_finance)
        self.assertFalse(treasurer.can_manage_points)
        self.assertFalse(treasurer.can_manage_tasks)
        self.assertFalse(treasurer.can_create_positions)
        self.assertFalse(treasurer.can_manage_nm_points)

        no_position = positions["No Position"]
        self.assertFalse(no_position.can_manage_roster)
        self.assertFalse(no_position.can_manage_finance)
        self.assertFalse(no_position.can_manage_points)
        self.assertFalse(no_position.can_manage_tasks)
        self.assertFalse(no_position.can_create_positions)
        self.assertFalse(no_position.can_manage_nm_points)

    def test_sends_approval_email_to_president(self):
        req = self.make_request(president_email="prez@example.com")
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["prez@example.com"])
        self.assertIn("Theta Chi", mail.outbox[0].subject)

    def test_already_approved_request_is_skipped(self):
        req = self.make_request(is_approved=True)
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        self.assertEqual(Chapter.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_running_twice_does_not_duplicate_chapter_or_positions(self):
        req = self.make_request()
        qs = ChapterRequest.objects.filter(pk=req.pk)
        approve_requests(None, None, qs)
        # Second run is a no-op because req.is_approved is now True and the
        # loop skips already-approved requests.
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        self.assertEqual(Chapter.objects.count(), 1)
        self.assertEqual(Position.objects.count(), 4)
        self.assertEqual(len(mail.outbox), 1)

    def test_existing_chapter_without_codes_gets_backfilled(self):
        # Simulates a chapter created some other way (e.g. manually in
        # admin) before a matching ChapterRequest gets approved.
        Chapter.objects.create(name="Theta Chi", university="UC Riverside")
        req = self.make_request()
        approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        self.assertEqual(Chapter.objects.count(), 1)
        chapter = Chapter.objects.get()
        self.assertIsNotNone(chapter.nm_invite_code)
        self.assertIsNotNone(chapter.active_invite_code)

    def test_two_requests_for_same_chapter_do_not_duplicate_positions(self):
        # H2: two separate requests (e.g. a double submit) for one chapter,
        # approved together, used to create every position twice.
        first = self.make_request()
        second = self.make_request()
        approve_requests(None, None, ChapterRequest.objects.filter(pk__in=[first.pk, second.pk]))
        chapter = Chapter.objects.get()
        self.assertEqual(Position.objects.filter(chapter=chapter).count(), 4)
        for title in ("President", "Vice President", "Treasurer", "No Position"):
            self.assertEqual(Position.objects.filter(chapter=chapter, title=title).count(), 1)

    def test_registration_works_after_duplicate_requests_are_approved(self):
        from users.forms import CustomUserCreationForm

        first = self.make_request()
        second = self.make_request()
        approve_requests(None, None, ChapterRequest.objects.filter(pk__in=[first.pk, second.pk]))
        chapter = Chapter.objects.get()
        password = "S0meStr0ngPass!23"
        member = CustomUserCreationForm(data={
            "username": "newmember", "email": "new@example.com",
            "first_name": "New", "last_name": "Member",
            "password1": password, "password2": password,
            "invite_code": chapter.nm_invite_code,
        })
        self.assertTrue(member.is_valid(), member.errors)
        self.assertEqual(member.save().position.title, "No Position")
        president = CustomUserCreationForm(data={
            "username": "pres", "email": "president@example.com",
            "first_name": "Pres", "last_name": "Ident",
            "password1": password, "password2": password,
            "invite_code": chapter.active_invite_code,
        })
        self.assertTrue(president.is_valid(), president.errors)
        self.assertEqual(president.save().position.title, "President")

    def test_email_failure_leaves_request_unapproved_and_creates_nothing(self):
        from unittest import mock

        req = self.make_request()
        with mock.patch("homepage.admin.send_mail", side_effect=OSError("smtp down")):
            with self.assertRaises(OSError):
                approve_requests(None, None, ChapterRequest.objects.filter(pk=req.pk))
        req.refresh_from_db()
        self.assertFalse(req.is_approved)
        self.assertEqual(Chapter.objects.count(), 0)
        self.assertEqual(Position.objects.count(), 0)
