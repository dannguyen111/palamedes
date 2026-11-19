from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MergeDuplicatePositionsMigrationTests(TransactionTestCase):
    """users.0004 merges duplicate positions so users.0005 can add the
    (chapter, title) unique constraint without failing on existing data."""

    migrate_from = [("users", "0003_position_can_manage_nm_points")]
    migrate_to = [("users", "0005_position_unique_title_per_chapter")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Chapter = old_apps.get_model("users", "Chapter")
        Position = old_apps.get_model("users", "Position")
        CustomUser = old_apps.get_model("users", "CustomUser")

        chapter = Chapter.objects.create(name="Pi Kappa", university="UCSD")
        self.keep = Position.objects.create(chapter=chapter, title="No Position")
        duplicate = Position.objects.create(chapter=chapter, title="No Position")
        Position.objects.create(chapter=chapter, title="President")
        self.on_keep = CustomUser.objects.create(username="a", position=self.keep, chapter=chapter)
        self.on_duplicate = CustomUser.objects.create(username="b", position=duplicate, chapter=chapter)
        self.chapter_id = chapter.id

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_duplicates_are_merged_into_the_oldest_position(self):
        Position = self.apps.get_model("users", "Position")
        self.assertEqual(
            Position.objects.filter(chapter_id=self.chapter_id, title="No Position").count(), 1
        )
        self.assertTrue(Position.objects.filter(pk=self.keep.pk).exists())
        self.assertEqual(Position.objects.filter(chapter_id=self.chapter_id).count(), 2)

    def test_members_of_deleted_duplicates_are_moved_not_dropped(self):
        CustomUser = self.apps.get_model("users", "CustomUser")
        self.assertEqual(CustomUser.objects.get(pk=self.on_keep.pk).position_id, self.keep.pk)
        self.assertEqual(CustomUser.objects.get(pk=self.on_duplicate.pk).position_id, self.keep.pk)
