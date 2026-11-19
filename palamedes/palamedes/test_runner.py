"""Test runner that swaps in local, manifest-free storage for the whole suite.

settings.py uses WhiteNoise's manifest storage for static files (needs a
collectstatic manifest that tests don't have) and switches uploads to S3 when
AWS keys are in .env. Tests must never depend on either, so every test run
gets plain local storage. Wired up via TEST_RUNNER in settings.py.
"""
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class LocalStorageTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._storage_override = override_settings(STORAGES=TEST_STORAGES)
        self._storage_override.enable()

    def teardown_test_environment(self, **kwargs):
        self._storage_override.disable()
        super().teardown_test_environment(**kwargs)
