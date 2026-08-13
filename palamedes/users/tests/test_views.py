import re

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from palamedes.test_helpers import PLAIN_STATIC_STORAGE, make_chapter_with_positions, make_user
from users.models import CustomUser


@PLAIN_STATIC_STORAGE
class RegisterViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()

    def valid_data(self, **overrides):
        data = {
            "username": "jdoe",
            "email": "jdoe@example.com",
            "first_name": "Jane",
            "last_name": "Doe",
            "password1": "S0meStr0ngPass!23",
            "password2": "S0meStr0ngPass!23",
            "invite_code": self.chapter.nm_invite_code,
        }
        data.update(overrides)
        return data

    def test_get_renders_empty_form(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/register.html")
        self.assertFalse(response.context["form"].is_bound)

    def test_valid_post_creates_inactive_user(self):
        self.client.post(reverse("register"), data=self.valid_data())
        user = CustomUser.objects.get(username="jdoe")
        self.assertFalse(user.is_active)

    def test_valid_post_sends_activation_email(self):
        self.client.post(reverse("register"), data=self.valid_data())
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["jdoe@example.com"])
        self.assertIn("activate", mail.outbox[0].body.lower())

    def test_valid_post_redirects_to_login(self):
        response = self.client.post(reverse("register"), data=self.valid_data())
        self.assertRedirects(response, reverse("login"))

    def test_invalid_post_rerenders_form_with_errors(self):
        response = self.client.post(
            reverse("register"), data=self.valid_data(invite_code="BADCODE1")
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/register.html")
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(CustomUser.objects.count(), 0)


@PLAIN_STATIC_STORAGE
class ActivateViewTests(TestCase):
    def setUp(self):
        self.chapter, self.positions = make_chapter_with_positions()
        self.user = make_user(
            chapter=self.chapter,
            position=self.positions["No Position"],
            is_active=False,
        )

    def activation_url(self, user, token):
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        return reverse("activate", kwargs={"uidb64": uid, "token": token})

    def test_valid_token_activates_and_logs_in(self):
        token = default_token_generator.make_token(self.user)
        response = self.client.get(self.activation_url(self.user, token))
        self.assertRedirects(response, reverse("dashboard"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
        # Logged in as this user afterward.
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_invalid_token_does_not_activate(self):
        response = self.client.get(self.activation_url(self.user, "bad-token"))
        self.assertRedirects(response, reverse("register"))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_malformed_uid_redirects_to_register(self):
        response = self.client.get(
            reverse("activate", kwargs={"uidb64": "not-valid-base64!!", "token": "sometoken"})
        )
        self.assertRedirects(response, reverse("register"))

    def test_nonexistent_uid_redirects_to_register(self):
        bogus_uid = urlsafe_base64_encode(force_bytes(999999))
        response = self.client.get(
            reverse("activate", kwargs={"uidb64": bogus_uid, "token": "sometoken"})
        )
        self.assertRedirects(response, reverse("register"))


@PLAIN_STATIC_STORAGE
class ProfileViewTests(TestCase):
    def setUp(self):
        self.user = make_user(
            email="jdoe@example.com", first_name="Jane", last_name="Doe"
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("profile"))
        self.assertRedirects(
            response, f"{reverse('login')}?next={reverse('profile')}"
        )

    def test_get_renders_form_prefilled_with_current_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("profile"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertEqual(response.context["p_form"].instance, self.user)

    def test_valid_post_updates_profile_and_redirects_to_self(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"),
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jdoe@example.com",
                "major": "Biology",
                "phone_number": "",
                "hometown": "",
                "bio": "",
            },
        )
        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.major, "Biology")

    def test_invalid_post_rerenders_form_with_errors(self):
        # first_name/last_name are blank=True on AbstractUser, so they're
        # not actually required by this ModelForm — an invalid email format
        # is what reliably fails validation here.
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("profile"),
            data={
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "not-an-email",
                "major": "",
                "phone_number": "",
                "hometown": "",
                "bio": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/profile.html")
        self.assertTrue(response.context["p_form"].errors)


@PLAIN_STATIC_STORAGE
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = make_user(username="jdoe", email="jdoe@example.com")

    def test_full_reset_flow_lets_user_set_new_password_and_log_in(self):
        response = self.client.post(
            reverse("password_reset"), data={"email": "jdoe@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r"(/password-reset-confirm/\S+/\S+/)", mail.outbox[0].body)
        self.assertIsNotNone(match, "no reset link found in the email body")
        reset_link = match.group(1)

        # First visit swaps the real token for a session-stored placeholder
        # and redirects there (Django's PasswordResetConfirmView behavior).
        response = self.client.get(reset_link, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "users/password_reset_confirm.html")
        self.assertTrue(response.context["validlink"])

        confirm_path = response.request["PATH_INFO"]
        response = self.client.post(
            confirm_path,
            data={
                "new_password1": "BrandNewStr0ngPass!9",
                "new_password2": "BrandNewStr0ngPass!9",
            },
            follow=True,
        )
        self.assertTemplateUsed(response, "users/password_reset_complete.html")

        self.assertTrue(
            self.client.login(username="jdoe", password="BrandNewStr0ngPass!9")
        )

    def test_reset_request_for_unknown_email_still_redirects_without_sending_email(self):
        # Django's PasswordResetView doesn't reveal whether an email exists.
        response = self.client.post(
            reverse("password_reset"), data={"email": "nobody@example.com"}
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)
