from django.apps import AppConfig


class BlogConfig(AppConfig):
    """Приложение со страницами публикаций."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'
    verbose_name = 'Блог'
