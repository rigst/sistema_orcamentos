from django.apps import AppConfig


class OrcamentosConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "orcamentos"

    def ready(self):
        # Import pelo efeito colateral: é ele que registra os receivers que
        # recalculam os totais do orçamento. O noqa é necessário — sem ele o
        # ruff trata como import não usado e o --fix apaga a linha, desligando
        # os signals sem aviso.
        import orcamentos.signals  # noqa: F401
