from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    name = 'organizations'

    def ready(self):
        import organizations.signals  # noqa: F401

    def ready(self):
        import organizations.signals  # noqa: F401
