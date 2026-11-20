from django.db import migrations
from django.db.models import Count, Min


def merge_duplicate_positions(apps, schema_editor):
    """Collapse positions that share a (chapter, title) into the oldest one.

    Approving two requests for the same chapter used to create every default
    position twice, which made registration crash. Members on a duplicate are
    moved to the kept position before the duplicate is deleted, so nobody
    loses their position. Runs before the unique constraint (next migration).
    """
    Position = apps.get_model('users', 'Position')
    CustomUser = apps.get_model('users', 'CustomUser')

    duplicates = (
        Position.objects.values('chapter_id', 'title')
        .annotate(n=Count('id'), keep_id=Min('id'))
        .filter(n__gt=1)
    )
    for group in duplicates:
        extra_ids = list(
            Position.objects.filter(chapter_id=group['chapter_id'], title=group['title'])
            .exclude(id=group['keep_id'])
            .values_list('id', flat=True)
        )
        CustomUser.objects.filter(position_id__in=extra_ids).update(position_id=group['keep_id'])
        Position.objects.filter(id__in=extra_ids).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_position_can_manage_nm_points'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_positions, migrations.RunPython.noop),
    ]
