"""Shared fixture builders for the test suites in homepage/users/dashboard.

Almost every test across all three apps needs a Chapter with the four
Position rows that `homepage.admin.approve_requests` normally creates, since
`users.forms.CustomUserCreationForm.save()` hard-depends on Position rows
titled exactly "President" and "No Position" existing for the chapter
(see docs/testing/codebase-notes.md, section 3/4). These helpers create that
state directly via the ORM instead of driving the admin action, so tests
stay fast and don't implicitly depend on admin internals.
"""
from users.models import Chapter, Position, CustomUser

POSITION_DEFAULTS = {
    "President": dict(
        can_manage_roster=True,
        can_manage_finance=True,
        can_manage_points=True,
        can_manage_tasks=True,
        can_create_positions=True,
        can_manage_nm_points=True,
    ),
    "Vice President": dict(
        can_manage_roster=True,
        can_manage_finance=False,
        can_manage_points=True,
        can_manage_tasks=True,
        can_create_positions=False,
        can_manage_nm_points=True,
    ),
    "Treasurer": dict(
        can_manage_roster=False,
        can_manage_finance=True,
        can_manage_points=False,
        can_manage_tasks=False,
        can_create_positions=False,
        can_manage_nm_points=False,
    ),
    "No Position": dict(
        can_manage_roster=False,
        can_manage_finance=False,
        can_manage_points=False,
        can_manage_tasks=False,
        can_create_positions=False,
        can_manage_nm_points=False,
    ),
}


def make_chapter(name="Theta Chi", university="UC Riverside", **kwargs):
    """A bare Chapter, no invite codes and no Position rows."""
    return Chapter.objects.create(name=name, university=university, **kwargs)


def make_chapter_with_positions(
    name="Theta Chi",
    university="UC Riverside",
    nm_invite_code="NMCODE01",
    active_invite_code="ACTCODE1",
):
    """A Chapter with invite codes plus the four standard Position rows,
    mirroring what homepage.admin.approve_requests creates in production.
    Returns (chapter, positions_by_title).
    """
    chapter = Chapter.objects.create(
        name=name,
        university=university,
        nm_invite_code=nm_invite_code,
        active_invite_code=active_invite_code,
    )
    positions = {
        title: Position.objects.create(chapter=chapter, title=title, **flags)
        for title, flags in POSITION_DEFAULTS.items()
    }
    return chapter, positions


_user_counter = 0


def make_user(
    chapter=None,
    position=None,
    status="ACT",
    username=None,
    password="testpass123!",
    **kwargs,
):
    """A CustomUser with sane defaults. Auto-generates a unique username if
    not given, since many tests create several users per test method.
    """
    global _user_counter
    _user_counter += 1
    if username is None:
        username = f"user{_user_counter}"
    user = CustomUser.objects.create_user(
        username=username,
        password=password,
        chapter=chapter,
        position=position,
        status=status,
        **kwargs,
    )
    return user
