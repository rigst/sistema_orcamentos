from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Max


class CategoriaItem(models.Model):
    COLOR_CHOICES = [
        ("#2563EB", "Azul"),
        ("#0F766E", "Verde petróleo"),
        ("#059669", "Verde"),
        ("#CA8A04", "Mostarda"),
        ("#EA580C", "Laranja"),
        ("#DC2626", "Vermelho"),
        ("#DB2777", "Rosa"),
        ("#7C3AED", "Violeta"),
        ("#4F46E5", "Índigo"),
        ("#475569", "Grafite"),
    ]

    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    cor = models.CharField(max_length=7, choices=COLOR_CHOICES, default="#2563EB")
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

    @classmethod
    def gerar_proximo_codigo(cls) -> str:
        prefixo = "CAT-ITEM-"
        ultimo_codigo = cls.objects.filter(codigo__startswith=prefixo).aggregate(max_codigo=Max("codigo"))["max_codigo"]
        sequencial = 1
        if ultimo_codigo:
            try:
                sequencial = int(str(ultimo_codigo).rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                sequencial = 1
        return f"{prefixo}{sequencial:04d}"

    def definir_codigo_automatico(self):
        if self.pk:
            codigo_original = type(self).objects.filter(pk=self.pk).values_list("codigo", flat=True).first()
            if codigo_original:
                self.codigo = codigo_original
                return
        self.codigo = self.gerar_proximo_codigo()

    def save(self, *args, **kwargs):
        self.definir_codigo_automatico()
        self.full_clean()
        super().save(*args, **kwargs)

# Create your models here.
