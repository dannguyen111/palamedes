from django.test import TestCase

from homepage.models import ChapterRequest
from users.forms import CustomUserCreationForm, ProfileUpdateForm
from users.models import Chapter, CustomUser, Position
from palamedes.test_helpers import make_chapter_with_positions, make_user


class CustomUserCreationFormTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()

    def valid_data(self, code, **overrides):
        data = {
            "username": "jdoe",
            "email": "jdoe@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password1": "S0meStr0ngPass!23",
            "password2": "S0meStr0ngPass!23",
            "invite_code": code,
        }
        data.update(overrides)
        return data

    def test_valid_data_with_nm_code_is_valid(self):
        form = CustomUserCreationForm(data=self.valid_data(self.chapter.nm_invite_code))
        self.assertTrue(form.is_valid(), form.errors)

    def test_valid_data_with_active_code_is_valid(self):
        form = CustomUserCreationForm(
            data=self.valid_data(self.chapter.active_invite_code)
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_duplicate_email_is_rejected(self):
        make_user(email="jdoe@example.com")
        form = CustomUserCreationForm(data=self.valid_data(self.chapter.nm_invite_code))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_invalid_invite_code_is_rejected(self):
        form = CustomUserCreationForm(data=self.valid_data("NOTREAL01"))
        self.assertFalse(form.is_valid())
        self.assertIn("invite_code", form.errors)

    def test_save_with_nm_code_assigns_chapter_no_position_and_nm_status(self):
        form = CustomUserCreationForm(data=self.valid_data(self.chapter.nm_invite_code))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.chapter, self.chapter)
        self.assertEqual(user.position, self.positions["No Position"])
        self.assertEqual(user.status, "NM")

    def test_save_with_active_code_assigns_chapter_no_position_and_act_status(self):
        form = CustomUserCreationForm(
            data=self.valid_data(self.chapter.active_invite_code)
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.chapter, self.chapter)
        self.assertEqual(user.position, self.positions["No Position"])
        self.assertEqual(user.status, "ACT")

    def test_save_matching_approved_chapter_request_forces_president_and_active(self):
        # Even when registering with the NM code, a matching approved
        # ChapterRequest (fraternity_name/university/president_email) forces
        # President + ACT — see codebase-notes.md §4.
        ChapterRequest.objects.create(
            fraternity_name=self.chapter.name,
            university=self.chapter.university,
            president_email="jdoe@example.com",
            is_approved=True,
        )
        form = CustomUserCreationForm(data=self.valid_data(self.chapter.nm_invite_code))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.position, self.positions["President"])
        self.assertEqual(user.status, "ACT")

    def test_save_with_unapproved_matching_chapter_request_does_not_force_president(self):
        ChapterRequest.objects.create(
            fraternity_name=self.chapter.name,
            university=self.chapter.university,
            president_email="jdoe@example.com",
            is_approved=False,
        )
        form = CustomUserCreationForm(data=self.valid_data(self.chapter.nm_invite_code))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.position, self.positions["No Position"])
        self.assertEqual(user.status, "NM")

    def test_save_raises_when_chapter_missing_no_position_row(self):
        # Pinning a known latent bug: save() hard-depends on a Position row
        # titled exactly "No Position" existing for the chapter. A chapter
        # created without the standard four positions (e.g. not via
        # approve_requests) breaks registration entirely.
        bare_chapter = Chapter.objects.create(
            name="Bare Chapter",
            university="Nowhere U",
            nm_invite_code="BARECODE1",
        )
        form = CustomUserCreationForm(data=self.valid_data("BARECODE1"))
        self.assertTrue(form.is_valid(), form.errors)
        with self.assertRaises(Position.DoesNotExist):
            form.save()


class ProfileUpdateFormTests(TestCase):
    def setUp(self):
        self.user = make_user(email="jdoe@example.com", first_name="Jane", last_name="Doe")

    def valid_data(self, **overrides):
        data = {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "jdoe@example.com",
            "major": "Computer Science",
            "phone_number": "5551234567",
            "hometown": "Riverside",
            "bio": "Hello!",
        }
        data.update(overrides)
        return data

    def test_valid_data_is_valid(self):
        form = ProfileUpdateForm(data=self.valid_data(), instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_save_updates_profile_fields(self):
        form = ProfileUpdateForm(
            data=self.valid_data(major="Biology"), instance=self.user
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.major, "Biology")

    def test_email_can_collide_with_another_users_email(self):
        # ProfileUpdateForm has no uniqueness check on email (unlike
        # CustomUserCreationForm.clean_email), and AbstractUser.email isn't
        # unique by default — pinning that this currently succeeds. See
        # codebase-notes.md §4.
        make_user(email="taken@example.com")
        form = ProfileUpdateForm(
            data=self.valid_data(email="taken@example.com"), instance=self.user
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(
            CustomUser.objects.filter(email="taken@example.com").count(), 2
        )
