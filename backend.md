# Palamedes — backend work list

A prioritised review of the Django backend, written as a practice checklist.
Every item names the file and line it came from, says *why* it matters, and
sketches the shape of the fix rather than handing over the code.

Line numbers are from the state of the repo when this was written; they will
drift as you edit.

**Not** covered here: templates, CSS, or anything in the frontend redesign.

---

## Legend

- 🔴 **Critical** — security, or money moving incorrectly. Do these first.
- 🟠 **High** — crashes, or data you can't get back.
- 🟡 **Medium** — correctness, performance, structure.
- ⚪ **Minor** — tidy-ups.

---

## 🔴 1. `dues_member` has no authentication or authorisation

**Where:** `dashboard/views.py:621`

```python
def dues_member(request, pk):
    brother = get_object_or_404(CustomUser, pk=pk)
    dues = Due.objects.filter(assigned_to=brother).order_by('is_paid', 'due_date')
```

It is the only view in the file without `@login_required`, and it has no
chapter check and no permission check either.

**Impact.** An anonymous visitor can walk `/dashboard/dues/brothers_due/1/`,
`/2/`, `/3/` … and read every member's full name, email address, and complete
charge history. This is both a missing-authentication bug and an insecure
direct object reference (IDOR).

**Fix — all three layers, not just the first:**

- [ ] Add `@login_required`
- [ ] Reject if `brother.chapter != request.user.chapter`
- [ ] Reject unless the viewer has `can_manage_finance` — a regular member has
      no business reading someone else's finances

Compare with `brother_profile` (`views.py:635`), which already does the chapter
check properly. Use it as the model.

---

## 🔴 2. `payment_success` never verifies the payment actually happened

**Where:** `dashboard/views.py:472-524`

```python
session = stripe.checkout.Session.retrieve(session_id)
...
if session.metadata['payment_type'] == 'bulk_payment':
```

The session is retrieved but `session.payment_status` is never checked, and
`session.metadata['user_id']` is never compared to `request.user.id`.

**Impact.** `session_id` arrives as a URL query parameter the user controls,
and a user can read their own session id straight off the Stripe checkout URL.
So the exploit is: press **Pay**, abandon the payment at Stripe, then visit
`/dashboard/dues/payment_success/?session_id=cs_test_…` by hand. The dues are
zeroed and nothing was ever charged.

There is a second problem in the single-payment branch:

```python
due = get_object_or_404(Due, pk=due_id)   # views.py:502 — not scoped to request.user
```

The bulk branch correctly scopes with `assigned_to=request.user`; this one does
not.

**Fix:**

- [ ] Bail out unless `session.payment_status == "paid"`
- [ ] Bail out unless `str(session.metadata.get("user_id")) == str(request.user.id)`
- [ ] Scope the single-payment lookup to `assigned_to=request.user`

---

## 🔴 3. Fulfilment happens in the success redirect instead of a webhook

**Where:** `dashboard/views.py:472-524`

The only thing that marks a due as paid is the browser landing on the success
URL. If the customer pays and then closes the tab — or their connection drops
on the redirect — Stripe has their money and Palamedes still shows the charge
as outstanding.

**Fix.** This is the standard Stripe pattern and worth learning properly:

- [ ] Add a webhook endpoint (e.g. `/dashboard/dues/stripe-webhook/`)
- [ ] Exempt it from CSRF (`@csrf_exempt`) — Stripe cannot send your token
- [ ] Verify the signature with `stripe.Webhook.construct_event(...)` against a
      `STRIPE_WEBHOOK_SECRET` read from the environment. **Never** trust the
      request body without this — anyone can POST to that URL
- [ ] Handle `checkout.session.completed` and do the fulfilment there
- [ ] Reduce the success page to display only; it must not mutate anything
- [ ] Test locally with the Stripe CLI: `stripe listen --forward-to localhost:8000/...`

---

## 🔴 4. `mark_paid` acts on a GET request

**Where:** `dashboard/views.py:536`

```python
def mark_paid(request, pk):
    due = get_object_or_404(Due, pk=pk)
    if request.user.position.can_manage_finance:
        amount = request.POST.get('amount')
        if not amount:
            payment_amount = due.amount   # ← full balance
```

There is no method check. On a GET, `request.POST.get('amount')` returns
`None`, so it falls into the `if not amount:` branch and marks the due **fully
paid**. A link-prefetching browser, a crawler following a link, or a crafted
URL sent to a treasurer is enough to wipe a balance.

**Fix:**

- [ ] Add `@require_POST` from `django.views.decorators.http`
- [ ] Audit every other state-changing view for the same pattern —
      `manage_point_request` and `edit_log_point` guard with
      `if request.method == 'POST'`, but a decorator is clearer and returns a
      correct `405` instead of silently redirecting

---

## 🔴 5. The bulk-payment idempotency guard is unreachable

**Where:** `dashboard/views.py:484-514`

```python
processed_sessions = request.session.get('processed_sessions', [])   # 484

if session.metadata['payment_type'] == 'bulk_payment':
    ...
    return render(...)                                               # 497  ← returns here

if session_id in processed_sessions:                                 # 510  ← never reached for bulk
```

The guard sits *after* the bulk branch has already returned, so a bulk payment
reprocesses on every refresh of the success page.

Two separate problems:

1. **Ordering** — the check must happen before any mutation, for both paths.
2. **Storage** — `request.session` is per browser session. Clearing cookies, or
   opening the link in another browser, defeats it entirely.

**Fix.** Don't patch the ordering — solve it with the database instead. See
item 6; a `unique=True` column on the Stripe session id makes double-processing
impossible at the storage layer, which is where idempotency belongs.

---

## 🟠 6. Payments destroy the charge record

**Where:** `dashboard/views.py:495` and `views.py:517`

```python
due.amount = 0          # bulk path
due.amount -= amount_paid   # single path
```

The `Due` row is mutated in place, so the original amount is gone. After
payment you can no longer answer "how much were spring dues?" — and this is why
the receipt page shows `Remaining: $0.00`. There is no record of *when* a
payment happened, *how much* was taken, or *who* recorded it.

**Fix — introduce a `Payment` model.** This is the single highest-value change
in this document; several other items dissolve once it exists.

```python
class Payment(models.Model):
    due = models.ForeignKey(Due, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    stripe_session_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
```

What this buys you:

- [ ] `Due.amount` becomes immutable — the charge is a fact, not a running total
- [ ] `remaining_balance` becomes a property: `self.amount - sum of payments`
- [ ] `is_paid` becomes derived rather than a field you must remember to set
- [ ] `unique=True` on `stripe_session_id` gives real idempotency (item 5) —
      a replay raises `IntegrityError` instead of double-crediting
- [ ] Receipts and payment history become truthful
- [ ] Partial payments start working properly

Write the data migration carefully: existing rows have already had `amount`
decremented, so you cannot reconstruct the original charges. Decide whether to
backfill a single `Payment` per paid due, or accept the loss for existing data
and start clean.

---

## 🟠 7. `due.remaining_balance` does not exist

**Where:** `dashboard/templates/dashboard/paid_treasurer.html` (both the hidden
input and the `max` attribute)

`Due` has no `remaining_balance` field or property. Django resolves an unknown
attribute to an empty string rather than raising, so the template renders:

```html
<input type="hidden" name="amount" value="">
```

The "pay full balance" button therefore submits an empty amount, which lands in
the `if not amount:` branch of `mark_paid` and pays the full balance anyway.
It works, but by accident, and the `max=""` means the custom-amount field has no
upper bound at all.

**Fix:**

- [ ] Add the property (falls out of item 6), or use `due.amount` in the
      template as an interim measure

This is a good illustration of why silent template failures are dangerous —
consider `string_if_invalid` in the `TEMPLATES` `OPTIONS` during development to
surface them.

---

## 🟠 8. `mark_paid` parses a decimal amount as an integer

**Where:** `dashboard/views.py:545`

```python
payment_amount = int(amount)
```

`Due.amount` is a `DecimalField(max_digits=10, decimal_places=2)` and the form
input is `step="0.01"`. Recording a payment of `85.50` raises `ValueError` and
shows the user *"Invalid payment amount. Please enter a whole number."*

**Fix:**

- [ ] Parse with `decimal.Decimal` and catch `decimal.InvalidOperation`
- [ ] Add an upper bound — nothing currently stops a treasurer entering more
      than is owed and driving the balance negative
- [ ] Never build money values through `float`; `int(float(amount) * 100)` at
      `views.py:435` has the same smell and should go through `Decimal` too

---

## 🟠 9. `user.position` is nullable but dereferenced without a guard

`CustomUser.position` is `null=True, blank=True`, and most ordinary members have
no position at all. Three views walk straight through it:

| File | Line | Effect |
|---|---|---|
| `dashboard/views.py` | 248 | `dues_dashboard` — the entire Dues page 500s |
| `dashboard/views.py` | 111 | `manage_point_request` |
| `dashboard/views.py` | 539 | `mark_paid` |

```python
is_treasurer = user.position.can_manage_finance   # AttributeError when position is None
```

Other views already do it correctly, which is the tell:

```python
if not (request.user.position and request.user.position.can_manage_points):   # views.py:652
```

**Fix — don't patch three call sites, fix it once.** Put the guard on the model
as properties:

```python
class CustomUser(AbstractUser):
    @property
    def can_manage_finance(self):
        return bool(self.position and self.position.can_manage_finance)
```

- [ ] Add a property per permission flag
- [ ] Replace every `request.user.position.<flag>` with `request.user.<flag>`
- [ ] Do the same thinking for `user.chapter`, which is also nullable — a user
      with no chapter is currently in a silently broken state rather than being
      redirected somewhere sensible

---

## 🟡 10. No `select_related` anywhere → N+1 queries

There is not a single `select_related` or `prefetch_related` call in the
project. Every foreign key touched in a template is a separate query.

| View | Relations touched per row | Rows |
|---|---|---|
| `points_hub` | `user`, `assigned_approver`, `submitted_by` | up to 100 |
| `directory` | `position` | whole chapter |
| `dashboard` | `announcement.author` | 5 |
| `unpaid_directory` | `position` | all debtors |

The points log alone costs roughly 300 extra queries per page load.

**Fix:**

- [ ] Install `django-debug-toolbar` **first**, and look at the query count
      before changing anything — watching the number drop is the part worth
      practising
- [ ] `points_hub`: `.select_related('user', 'assigned_approver', 'submitted_by')`
- [ ] `directory` / `unpaid_directory`: `.select_related('position')`
- [ ] `dashboard`: `.select_related('author')` on the announcements query

Note the annotation in `unpaid_directory` (`views.py:597`) is **correct** —
`filter()` before `annotate()` constrains the join, so `Sum('dues__amount')`
sums only unpaid rows. Verified empirically; leave it alone. If you want it to
be obvious to the next reader, the explicit form is
`Sum('dues__amount', filter=Q(dues__is_paid=False))`.

---

## 🟡 11. Bulk operations loop instead of batching, and aren't atomic

**Where:** `dashboard/views.py:693` (`manage_points_creation`) and
`_helper_bulk_transaction` (`views.py:281`)

```python
for u in users_to_update:
    HousePoint.objects.create(...)     # one INSERT per member
```

There is no `transaction.atomic` anywhere in the project, so a failure partway
through a chapter-wide charge leaves half the members billed and half not, with
a success message either way.

**Fix:**

- [ ] Build a list and use `bulk_create()`
- [ ] Wrap both bulk helpers in `transaction.atomic()`
- [ ] Report the real count from the result rather than a counter incremented
      in the loop

---

## 🟡 12. Business logic lives in the views

**Where:** `dashboard/views.py:106-159` (`manage_point_request`)

Roughly forty lines of status juggling — approve, reject, counter, and the
"swap" logic that bounces a request between submitter and approver — sit inside
a view function, interleaved with `messages.*` calls. It cannot be tested
without going through HTTP.

**Fix:**

- [ ] Move the transitions onto the model:
      `HousePoint.approve(by)`, `.reject(by, reason)`, `.counter(by, amount, reason)`
- [ ] Let each method enforce its own preconditions and raise on an invalid
      transition, rather than silently doing nothing
- [ ] Leave the view to do permissions, call the method, and set a message

Related: `_helper_single_transaction` and `_helper_bulk_transaction` return
either `None` or a redirect, and the caller does `if result: return result`
(`views.py:334`, `:358`). That control flow is hard to follow and easy to get
wrong — prefer raising, or returning an explicit result object.

---

## 🟡 13. Model-level constraints are missing

**Where:** `dashboard/models.py`

- `HousePoint.amount` is an unbounded `IntegerField` — nothing stops a
  999,999-point request, or a negative one where it isn't intended
- `Due` has no index on `assigned_to` / `is_paid`, which is the pair filtered on
  nearly every page
- No `Meta.ordering` on any model, so unordered querysets can come back in
  different orders between runs (and paginate incorrectly later)
- `Due.is_template` exists but nothing in the codebase reads it — either use it
  or drop it

**Fix:**

- [ ] Add validators or `PositiveIntegerField` where negatives are meaningless
- [ ] Add `class Meta: ordering = [...]` to each model
- [ ] Add a composite index on `Due(assigned_to, is_paid)`
- [ ] Consider `CheckConstraint` for invariants the database should enforce

---

## 🟡 14. No tests

All three `tests.py` files are the empty three-line Django stub. `manage.py
test` reports *"Ran 0 tests"*. (Note: `CLAUDE.md` refers to a
`users.tests.RegistrationTest` — it does not exist.)

Given this application moves money, start where the risk is. Each of these maps
onto a bug above, so they should **fail before the fix and pass after** — which
is the most satisfying way to practise:

- [ ] `payment_success` with an *unpaid* Stripe session leaves the due untouched
- [ ] Replaying the same `session_id` records one payment, not two
- [ ] `dues_member` returns 403 for a non-treasurer, and for a different chapter
- [ ] `mark_paid` accepts `85.50`
- [ ] `dues_dashboard` loads for a user whose `position` is `None`
- [ ] `manage_point_request` permission matrix: approver / exec / submitter /
      unrelated member

Use `unittest.mock.patch` on the `stripe` calls so tests never hit the network.

---

## ⚪ 15. Settings and configuration

**Where:** `palamedes/settings.py`

- [ ] `STRIPE_PUBLIC_KEY` is hardcoded at line 150. It is a test *publishable*
      key so nothing is leaked, but it should come from the environment like
      `STRIPE_SECRET_KEY` does — otherwise test keys ship to production
- [ ] `SECRET_KEY` falls back to `'default-insecure-key-for-dev'` (line 26).
      Fine locally; make it raise when `DEBUG=False`
- [ ] Add `STRIPE_WEBHOOK_SECRET` for item 3
- [ ] `STATIC_ROOT` (`palamedes/staticfiles/`) is **not** in `.gitignore` —
      add it before the first `collectstatic` on a real deploy
- [ ] Run `manage.py check --deploy` and work through what it reports
      (`SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
      `SECURE_SSL_REDIRECT`) behind a `if not DEBUG:` block

---

## Suggested order

1. **Items 1 and 4** — one decorator each, closes the two worst holes today
2. **Item 2** — a few lines, stops free dues
3. **Item 9** — model properties, kills the most common 500
4. **Item 6** — the `Payment` model; items 5, 7 and 8 largely fall out of it
5. **Item 3** — the Stripe webhook, once `Payment` exists to fulfil into
6. **Item 14** — tests, locking in everything above
7. **Items 10-13** — performance and structure, once behaviour is correct

Items 1-4 are roughly an evening. Item 6 is the interesting one and worth
taking slowly, because it is a genuine schema design exercise with a migration
that has to deal with data you have already lost.
