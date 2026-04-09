from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class CategoriaItem(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Categoria de item"
        verbose_name_plural = "Categorias de itens"

    def __str__(self):
        return self.nome


class ItemCatalogo(models.Model):
    UNIDADE_CHOICES = [
        ("un", "Unidade"),
        ("hr", "Hora"),
        ("dia", "Diária"),
        ("m", "Metro"),
        ("m2", "Metro quadrado"),
        ("m3", "Metro cúbico"),
        ("kg", "Quilo"),
        ("cx", "Caixa"),
        ("pct", "Pacote"),
        ("sv", "Serviço"),
    ]

    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255)
    descricao_padrao = models.TextField(blank=True)

    categoria = models.ForeignKey(
        CategoriaItem,
        on_delete=models.PROTECT,
        related_name="itens",
        null=True,
        blank=True,
    )

    unidade_medida = models.CharField(
        max_length=10,
        choices=UNIDADE_CHOICES,
        default="un",
    )

    valor_unitario_padrao = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    observacoes = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "Item de catálogo"
        verbose_name_plural = "Itens de catálogo"

    def __str__(self):
        return f"{self.codigo} - {self.nome}"

# Create your models here.
