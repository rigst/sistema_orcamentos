"""Versões do orçamento: cada alteração salva vira um retrato, e desfazer ou
refazer restaura um retrato anterior ou seguinte.

Fica num módulo próprio e é importado pelo `models.py` do app para o Django
registrar o modelo.
"""

from django.conf import settings
from django.db import models


class VersaoOrcamento(models.Model):
    """Retrato do orçamento (dados gerais e itens) depois de uma alteração.

    A versão atual é a mais recente não desfeita. Desfazer marca a atual como
    desfeita e restaura a anterior; refazer reativa a desfeita mais antiga.
    Uma alteração nova depois de desfazer apaga as desfeitas, como em qualquer
    editor: o ramo desfeito deixa de existir.
    """

    orcamento = models.ForeignKey(
        "orcamentos.Orcamento", on_delete=models.CASCADE, related_name="versoes"
    )
    descricao = models.CharField(max_length=200)
    dados = models.JSONField()
    desfeita = models.BooleanField(default=False)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)
        indexes = [models.Index(fields=["orcamento", "desfeita", "id"])]

    def __str__(self):
        return f"{self.orcamento_id} #{self.pk}: {self.descricao}"
