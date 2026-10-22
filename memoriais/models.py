from django.conf import settings
from django.db import models


class ImportacaoMemorial(models.Model):
    """Uma leitura de memorial descritivo pela IA, ligada a um orçamento.

    O arquivo em si não é guardado: ele vive só na memória do processo durante a
    chamada. Fica o rastro do que a IA leu e decidiu (`resultado`), para o
    usuário conferir item a item o que entrou no orçamento e por quê.
    """

    STATUS_CHOICES = [
        ("pendente", "Na fila"),
        ("processando", "Lendo o memorial"),
        ("concluida", "Concluída"),
        ("erro", "Falhou"),
    ]
    EM_ANDAMENTO = ("pendente", "processando")

    orcamento = models.ForeignKey(
        "orcamentos.Orcamento",
        on_delete=models.CASCADE,
        related_name="importacoes_memorial",
    )
    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="importacoes_memorial",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="importacoes_memorial",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    arquivo_nome = models.CharField(max_length=255, blank=True)
    instrucoes = models.TextField(blank=True)
    preencher_evento = models.BooleanField(default=True)
    incluir_fora_catalogo = models.BooleanField(default=True)

    resultado = models.JSONField(default=dict, blank=True)
    erro = models.TextField(blank=True)
    itens_criados = models.PositiveIntegerField(default=0)
    modelo = models.CharField(max_length=60, blank=True)
    tokens_entrada = models.PositiveIntegerField(default=0)
    tokens_saida = models.PositiveIntegerField(default=0)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "importação de memorial"
        verbose_name_plural = "importações de memorial"

    def __str__(self):
        return f"{self.arquivo_nome or 'texto colado'} ({self.orcamento.numero})"

    @property
    def em_andamento(self):
        return self.status in self.EM_ANDAMENTO
