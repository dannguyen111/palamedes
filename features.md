# Palamedes — Feature Roadmap

Ideas for what to build next, grounded in what's actually in the repo today. Ordered
roughly by value-per-hour: Tier 0 is finishing things you already started, Tier 1 is the
features a chapter would notice missing, Tier 2 is what would make Palamedes better than a
spreadsheet + GroupMe, Tier 3 is platform work.

---

## Where the app stands today

**Shipped and working:**

| Area | State |
|---|---|
| Chapter onboarding | Public request form → admin action generates invite codes, creates chapter + 4 default positions, emails the president |
| Registration | Invite-code gated, email-verified, auto-assigns NM vs Active from which code was used, auto-promotes the approved president |
| Profiles | Editable profile, photo upload (S3 in prod), chapter directory with search + status filter, individual brother profile pages |
| House points | Submit → approve / reject / counter negotiation loop, direct assignment, bulk assignment by group, leaderboards (NM + Active), filterable master log, log editing |
| Dues | Single + bulk charge creation, Stripe checkout (single and multi-item), treasurer manual payment recording, unpaid-member directory, per-member dues detail |
| Permissions | 6 boolean flags on `Position`, checked at the view level |

**Built but not wired up** — these are models with admin registration and nothing else:

- `Task` — no view, no URL, no form, no template. `dashboard.html` displays a
  `pending_tasks_count` that nobody can ever change.
- `Announcement` — the dashboard renders the latest 5, but there is no way to post one
  outside the Django admin.
- `can_manage_roster`, `can_manage_tasks`, `can_create_positions` — defined on `Position`,
  never read by any view.
- `Due.is_template` — set on the model, never used.
- `dashboard/templates/dashboard/inbox.html` and `ledger.html` exist; their URLs are
  commented out in `dashboard/urls.py:9,11`.

---

## Tier 0 — Finish what's half-built

Highest value per hour of work in the whole document. The data model is already there.

### 0.1 Tasks

The model, the admin, the dashboard counter, and the `can_manage_tasks` permission all
exist. Missing: everything a user touches.

- `assign_task` view (gated on `can_manage_tasks`), `my_tasks` list, `complete_task` toggle
- Task detail with description, due date, assigner
- Overdue styling on the dashboard tile
- Bulk assign, reusing the `target_group` pattern already in `BulkDueForm` / `BulkPointForm`

Worth adding to the model: `chapter` FK (for scoping — `Task` currently has no chapter, so
cross-chapter leakage is possible), `completed_at`, and an optional `points_reward` that
mints an approved `HousePoint` when the task is marked done.

### 0.2 Announcements

- `create_announcement` / `edit` / `delete`, gated on a new `can_post_announcements` flag
  (or reuse `can_manage_roster` short-term)
- Full announcements list page, not just the dashboard's top 5
- `is_pinned` and `expires_at` fields
- Optional email/push fan-out to the chapter

### 0.3 Roster management

`can_manage_roster` exists and does nothing. Officers currently need Django admin access to
change anyone's position — which is a real problem, since that means handing out superuser.

- Roster page: change a member's `position`, promote NM → Active, deactivate/remove
- Bulk NM → Active promotion at initiation (a once-a-semester ritual, currently 30 manual
  admin edits)
- `pledge_semester` / `pledge_year` are on `CustomUser` but never editable in the app —
  they're needed for the `PLEDGE_CLASS` bulk-target option to work at all

### 0.4 Position editor

`can_create_positions` is the President-only flag with no UI. Every chapter has officers
beyond President/VP/Treasurer — Recruitment Chair, Social Chair, Pledge Educator, Risk
Manager, Scholarship Chair. Right now they can't exist.

- Create/edit/delete positions with the 6 permission checkboxes
- Guard rails: can't delete a position that has members, can't remove the last President
- Consider `Position.is_default` so the four seeded roles can't be deleted

### 0.5 Chapter settings page

The president receives invite codes in one email at approval time. If they lose it, the
codes are unrecoverable without admin access.

- View current NM + Active invite codes
- Regenerate codes (important — codes leak to non-members)
- Edit chapter name / university, upload a chapter crest
- Set a per-semester points requirement (feeds Tier 1.2)

### 0.6 Revive or delete `inbox.html` / `ledger.html`

Two templates, ~200 lines, with commented-out URLs. Either finish them (a unified inbox
across points/tasks/dues would be genuinely useful) or delete them so they stop looking
like live code.

---

## Tier 1 — The features a chapter will ask for

### 1.1 Events + attendance

**The biggest gap in the product.** Points in a real chapter are earned by showing up.
Right now every point is typed in by hand as free text, which means the point system is
really just a shared notepad.

```
Event
  chapter, title, description, category (CHAPTER/SOCIAL/PHILANTHROPY/RECRUITMENT/BROTHERHOOD)
  starts_at, ends_at, location
  is_mandatory, points_value
  created_by

Attendance
  event, user
  status (PRESENT / LATE / EXCUSED / ABSENT)
  checked_in_at, recorded_by
```

What this unlocks:

- Chapter calendar (month + list view) on the dashboard
- Check-in: QR code posted at the door, or officer taps names off a roster
- **Auto-points**: marking someone PRESENT at an event mints an approved `HousePoint`
  linked to that event — replacing most manual point entry
- Excused-absence requests with an approval flow (reuse the `HousePoint` PENDING →
  APPROVED/REJECTED pattern, it's the same shape)
- Attendance rate per member, per event type — the number every exec board wants
- Fines for unexcused absences from mandatory events → auto-creates a `Due`

Add `event` as a nullable FK on `HousePoint` so points can point back to their source.

### 1.2 Semesters / terms

Nothing in the app resets. Points accumulate forever, leaderboards are all-time, and there's
no notion of "this semester's requirement."

```
Term
  chapter, name ("Fall 2026"), starts_on, ends_on, is_current
  points_required   # e.g. 25 to be in good standing
```

- Add `term` FK to `HousePoint`, `Due`, `Event`
- Term switcher on the points hub and leaderboards
- **Good standing indicator**: points earned vs. required, dues paid vs. owed — one badge
  per member, visible in the directory
- Historical archive: "Spring 2026 final standings"
- End-of-term rollover action

`HousePoint.date_for` already exists, so terms can be backfilled by date range.

### 1.3 Payment ledger + Stripe webhook

Two real problems in the current dues code:

1. **Payments are destructive.** `mark_paid` does `due.amount -= payment_amount`
   (`dashboard/views.py:553`), and the bulk success path sets `due.amount = 0`
   (`views.py:495`). The original charge amount is overwritten, so there is no record of
   what was actually owed or what was actually paid. A treasurer cannot reconcile.
2. **Payment confirmation depends on the browser.** `payment_success` fires only if the
   user lands back on the success URL. Close the tab after paying and the charge stays
   unpaid in the database.

Fix both with a payment record:

```
Payment
  due, user, amount
  method (STRIPE / CASH / VENMO / CHECK)
  stripe_session_id (unique), stripe_payment_intent
  recorded_by, created_at, note
```

- `Due.amount` becomes immutable; `amount_paid` is `Sum(payments)`, `balance` is derived
- Stripe webhook endpoint on `checkout.session.completed` — the actual correct way to do
  this, and it makes the `processed_sessions` session-key idempotency hack unnecessary
- Payment history per member, receipt emails, refund/void with a reason
- Also worth adding: `Due.chapter` FK (dues are currently only chapter-scoped transitively
  through `assigned_to`)

### 1.4 Notifications

Nothing notifies anyone of anything. A point request can sit in a queue for a month.

- In-app notification bell: point request awaiting your approval, counter-offer returned,
  new due assigned, task assigned, task due tomorrow, announcement posted
- Email digest (daily or weekly), with per-user opt-out preferences
- Dues reminders on a schedule: 7 days out, day-of, overdue
- Later: SMS via Twilio for mandatory-event reminders, push via web push

```
Notification
  user, verb, target (generic FK), url, is_read, created_at
NotificationPreference
  user, channel, category, enabled
```

### 1.5 Treasurer reporting + exports

The treasurer is the user with the most to lose from bad tooling.

- Chapter financial summary: total billed, collected, outstanding, collection rate
- Aging report — who is 30/60/90 days late
- CSV export of dues, payments, points, roster, attendance
- Budget vs. actual by category, if you add an `Expense` model
- Printable/PDF statement per member

### 1.6 Dues quality-of-life

- **Payment plans**: split one charge into scheduled installments
- **Late fees**: auto-add after N days past due
- Financial holds — flag members who are delinquent, surface in the directory
- Recurring/templated dues (`Due.is_template` was clearly meant for this)
- Waivers and scholarships with an approval trail
- Venmo/Zelle "I paid outside the app" claim → treasurer confirms

---

## Tier 2 — What makes this better than a spreadsheet

### 2.1 Study hours / scholarship tracking

Nearly every national organization requires new members to log study hours, and it's
tracked in a Google Sheet at 99% of chapters.

```
StudyHours
  user, term, hours, location, date, verified_by, status
```

Weekly requirement per member, progress bar, scholarship-chair verification queue. GPA
tracking with self-reported or uploaded transcripts, chapter GPA average, semester trend.

### 2.2 Service / philanthropy hours

Same shape as study hours but usually reported up to nationals, so exports matter more.

```
ServiceHours
  user, term, organization, hours, date, description, verified_by, status
PhilanthropyEvent
  chapter, name, date, funds_raised, beneficiary
```

Chapter totals, per-member totals, "hours + dollars raised this semester" for the annual
report.

### 2.3 Committees

Chapters organize by committee (recruitment, social, risk, standards). Right now the only
grouping is NM vs. Active.

```
Committee
  chapter, name, chair (FK to user), description
CommitteeMembership
  committee, user, role
```

Committee-scoped tasks, announcements, and events. Committee-only pages.

### 2.4 Voting / elections

Officer elections and chapter votes happen every semester and are run on paper.

```
Poll
  chapter, question, type (SINGLE/MULTI/RANKED), opens_at, closes_at, is_anonymous, quorum
PollOption / Vote
```

Anonymous ballots, quorum tracking, results published after close. Also useful for bid
votes during recruitment and standards-board decisions.

### 2.5 Recruitment / rush pipeline

Currently a PNM only becomes visible after they already have an invite code.

```
Rushee
  chapter, name, email, phone, year, major, referred_by
  stage (PROSPECT → INVITED → INTERVIEWED → BID_EXTENDED → ACCEPTED → DECLINED)
  notes, rating
```

Kanban board by stage, per-brother notes and ratings, bid vote integration, and — the nice
payoff — converting an accepted rushee into a `CustomUser` with the NM invite code
pre-attached.

### 2.6 Standards / judicial board

The disciplinary process is sensitive and universally handled over text.

- Incident report submission (optionally anonymous)
- Standards board case tracking with a status workflow
- Sanctions: fines that create a `Due`, point deductions, probation flags
- Strict visibility — only board members, with an audit log of every view

### 2.7 Documents + resources

Bylaws, risk-management policy, meeting minutes, the pledge manual. Currently distributed
by Google Drive link in a group chat.

```
Document
  chapter, title, file, category, uploaded_by, visibility (ALL/ACTIVES/EXEC)
```

Meeting minutes as first-class objects, with attendance pulled from the event record.

### 2.8 Alumni

- Alumni status on `CustomUser` (graduated members currently just... stay Active forever)
- Alumni directory with grad year, employer, city — genuinely valuable for the members
- Alumni-only announcements, donation tracking, mentorship matching

---

## Tier 3 — Platform work

### 3.1 Tests

`dashboard/tests.py`, `users/tests.py`, and `homepage/tests.py` are 3-line stubs. Given the
permission logic scattered through views and a payment flow handling real money, this is
the most important item in Tier 3.

Start with: the points approval state machine, every permission gate, the Stripe flow
(mocked), invite-code registration, and chapter data isolation.

### 3.2 Chapter data isolation audit

Several views fetch by pk without confirming the object belongs to the requester's chapter
— `dues_member` (`views.py:621`, also missing `@login_required`), `mark_paid`,
`make_payment_treasurer`, `edit_log_point`. `brother_profile` does check, which is the
pattern to copy everywhere. Worth a systematic pass plus a reusable
`@chapter_scoped` decorator or a manager method.

### 3.3 Audit log

Who edited that point log? Who deleted the due? Who changed a position?

```
AuditEntry
  chapter, actor, action, target (generic FK), before, after, ip, created_at
```

Especially important for point-log edits and any financial mutation.

### 3.4 Onboarding

New chapters land in an empty app. A setup checklist — invite members, create positions,
set the term, post the first announcement — plus a demo/sandbox mode for the sales pitch.

### 3.5 Multi-chapter / nationals tier

A `Nationals` org above `Chapter`, with read-only rollup dashboards, cross-chapter
compliance reporting, and standardized required-hours settings. This is the actual revenue
model for a product like this.

### 3.6 API + mobile

DRF-backed JSON API and a React Native or PWA client. Members live on their phones; the
tabbar is a good start but a real app is what gets daily usage. Push notifications and QR
event check-in are the two features that justify it.

### 3.7 Ops

- Rate limiting on registration and password reset
- Stripe webhook signature verification (once 1.3 lands)
- Move `STRIPE_PUBLIC_KEY` out of `settings.py:150` into an env var, matching the secret key
- Soft deletes on members and dues
- Background jobs (Celery or `django-q`) for email fan-out, reminders, late fees
- Sentry, structured logging, database backups

---

## Suggested build order

If you want a single path through this:

1. **Tasks + Announcements** (Tier 0.1, 0.2) — models exist, ship in a weekend
2. **Roster + Position management** (0.3, 0.4) — gets officers out of Django admin
3. **Payment ledger + Stripe webhook** (1.3) — fixes a live correctness bug
4. **Events + attendance** (1.1) — the feature that changes what the product is
5. **Terms + good standing** (1.2) — makes points and dues mean something
6. **Notifications** (1.4) — turns a site people visit into one that pulls them back
7. **Tests** (3.1) — realistically, alongside 3 and 4, not after
