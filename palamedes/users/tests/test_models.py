from django.db import IntegrityError, transaction
from django.test import TestCase

from users.models import Chapter, Position, CustomUser


class ChapterModelTests(TestCase):
    def test_str_includes_name_and_university(self):
        chapter = Chapter.objects.create(name="Theta Chi", university="UC Riverside")
        self.assertEqual(str(chapter), "Theta Chi - UC Riverside")

    def test_invite_codes_default_to_null(self):
        chapter = Chapter.objects.create(name="Theta Chi", university="UC Riverside")
        self.assertIsNone(chapter.nm_invite_code)
        self.assertIsNone(chapter.active_invite_code)

    def test_multiple_chapters_can_have_null_invite_codes(self):
        # unique=True + null=True allows multiple NULLs under Django/SQLite's
        # unique constraint semantics.
        Chapter.objects.create(name="Theta Chi", university="UC Riverside")
        Chapter.objects.create(name="Sigma Nu", university="UC Riverside")
        self.assertEqual(Chapter.objects.count(), 2)

    def test_duplicate_nm_invite_code_across_chapters_raises_integrity_error(self):
        Chapter.objects.create(
            name="Theta Chi", university="UC Riverside", nm_invite_code="DUPE1234"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Chapter.objects.create(
                    name="Sigma Nu",
                    university="UC Riverside",
                    nm_invite_code="DUPE1234",
                )

    def test_duplicate_active_invite_code_across_chapters_raises_integrity_error(self):
        Chapter.objects.create(
            name="Theta Chi", university="UC Riverside", active_invite_code="DUPE1234"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Chapter.objects.create(
                    name="Sigma Nu",
                    university="UC Riverside",
                    active_invite_code="DUPE1234",
                )


class PositionModelTests(TestCase):
    def setUp(self):
        self.chapter = Chapter.objects.create(name="Theta Chi", university="UC Riverside")

    def test_str_includes_title_and_chapter_name(self):
        position = Position.objects.create(chapter=self.chapter, title="President")
        self.assertEqual(str(position), "President (Theta Chi)")

    def test_permission_flags_default_to_false(self):
        position = Position.objects.create(chapter=self.chapter, title="No Position")
        self.assertFalse(position.can_manage_roster)
        self.assertFalse(position.can_manage_finance)
        self.assertFalse(position.can_manage_points)
        self.assertFalse(position.can_manage_tasks)
        self.assertFalse(position.can_create_positions)
        self.assertFalse(position.can_manage_nm_points)

    def test_duplicate_titles_within_same_chapter_are_permitted(self):
        # No unique_together on (chapter, title) at the model level, even
        # though app logic (Position.objects.get(...) in
        # CustomUserCreationForm.save()) assumes uniqueness of well-known
        # titles per chapter. Pinning the model's permissive behavior here —
        # see codebase-notes.md §4.
        Position.objects.create(chapter=self.chapter, title="President")
        Position.objects.create(chapter=self.chapter, title="President")
        self.assertEqual(
            Position.objects.filter(chapter=self.chapter, title="President").count(), 2
        )


class CustomUserModelTests(TestCase):
    def setUp(self):
        self.chapter = Chapter.objects.create(name="Theta Chi", university="UC Riverside")

    def test_str_uses_full_name_when_present(self):
        user = CustomUser.objects.create_user(
            username="jdoe", password="pw", first_name="Jane", last_name="Doe"
        )
        self.assertEqual(str(user), "Jane Doe (jdoe)")

    def test_str_falls_back_to_username_without_full_name(self):
        user = CustomUser.objects.create_user(username="jdoe", password="pw")
        self.assertEqual(str(user), "jdoe")

    def test_status_defaults_to_new_member(self):
        user = CustomUser.objects.create_user(username="jdoe", password="pw")
        self.assertEqual(user.status, "NM")

    def test_image_defaults_to_default_jpg(self):
        user = CustomUser.objects.create_user(username="jdoe", password="pw")
        self.assertEqual(user.image.name, "default.jpg")

    def test_chapter_and_position_are_optional(self):
        user = CustomUser.objects.create_user(username="jdoe", password="pw")
        self.assertIsNone(user.chapter)
        self.assertIsNone(user.position)

    def test_position_survives_when_chapter_deleted_is_not_the_case(self):
        # chapter FK is CASCADE: deleting the chapter deletes the member.
        user = CustomUser.objects.create_user(
            username="jdoe", password="pw", chapter=self.chapter
        )
        self.chapter.delete()
        self.assertFalse(CustomUser.objects.filter(pk=user.pk).exists())

    def test_position_set_null_when_position_deleted(self):
        position = Position.objects.create(chapter=self.chapter, title="President")
        user = CustomUser.objects.create_user(
            username="jdoe", password="pw", chapter=self.chapter, position=position
        )
        position.delete()
        user.refresh_from_db()
        self.assertIsNone(user.position)
