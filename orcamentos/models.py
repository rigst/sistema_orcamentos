from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


DUAS_CASAS = Decimal("0.01")


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


class Orcamento(models.Model):
    STATUS_CHOICES = [
        ("rascunho", "Rascunho"),
        ("em_elaboracao", "Em elaboração"),
        ("enviado", "Enviado"),
        ("aprovado", "Aprovado"),
        ("rejeitado", "Rejeitado"),
        ("cancelado", "Cancelado"),
    ]

    numero = models.CharField(max_length=30, unique=True)

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="orcamentos",
    )

    titulo = models.CharField(max_length=255)
    descricao_inicial = models.TextField(blank=True)
    observacoes_gerais = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="rascunho",
    )

    data_emissao = models.DateField()
    validade_em = models.DateField(null=True, blank=True)

    subtotal_itens = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    desconto_global_valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    desconto_global_percentual = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    acrescimo_global_valor = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    acrescimo_global_percentual = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    total_final = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    mostrar_ajustes_no_relatorio = models.BooleanField(
        default=False,
        help_text="Se marcado, o relatório do cliente mostra descontos e acréscimos detalhados.",
    )

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orcamentos_criados",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orcamentos_atualizados",
        null=True,
        blank=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-criado_em"]

    def __str__(self):
        return f"{self.numero} - {self.cliente}"

    def clean(self):
        if self.validade_em and self.validade_em < self.data_emissao:
            raise ValidationError(
                {"validade_em": "A validade não pode ser anterior à data de emissão."}
            )

    def calcular_subtotal_itens(self) -> Decimal:
        total = sum((item.subtotal for item in self.itens.all()), Decimal("0.00"))
        return arredondar(total)

    def calcular_total_final(self) -> Decimal:
        subtotal = self.calcular_subtotal_itens()

        desconto_percentual_valor = arredondar(
            subtotal * (self.desconto_global_percentual / Decimal("100"))
        )
        acrescimo_percentual_valor = arredondar(
            subtotal * (self.acrescimo_global_percentual / Decimal("100"))
        )

        total = (
            subtotal
            - self.desconto_global_valor
            - desconto_percentual_valor
            + self.acrescimo_global_valor
            + acrescimo_percentual_valor
        )

        if total < Decimal("0.00"):
            total = Decimal("0.00")

        return arredondar(total)

    def recalcular_totais(self, salvar: bool = True):
        self.subtotal_itens = self.calcular_subtotal_itens()
        self.total_final = self.calcular_total_final()

        if salvar:
            self.save(update_fields=["subtotal_itens", "total_final", "atualizado_em"])


class ItemOrcamento(models.Model):
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

    orcamento = models.ForeignKey(
        Orcamento,
        on_delete=models.CASCADE,
        related_name="itens",
    )

    item_catalogo = models.ForeignKey(
        "catalogo.ItemCatalogo",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="itens_em_orcamentos",
    )

    ordem = models.PositiveIntegerField(default=1)

    codigo_item = models.CharField(max_length=50, blank=True)
    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)
    unidade_medida = models.CharField(max_length=10, choices=UNIDADE_CHOICES, default="un")

    quantidade = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("1.00"),
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    valor_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    desconto_valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    desconto_percentual = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[
            MinValueValidator(Decimal("0.00")),
            MaxValueValidator(Decimal("100.00")),
        ],
    )

    acrescimo_valor = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    acrescimo_percentual = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    observacoes = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordem", "id"]

    def __str__(self):
        return f"{self.nome} ({self.orcamento.numero})"

    def clean(self):
        valor_base = self.quantidade * self.valor_unitario

        desconto_percentual_valor = arredondar(
            valor_base * (self.desconto_percentual / Decimal("100"))
        )
        desconto_total = self.desconto_valor + desconto_percentual_valor

        if desconto_total > valor_base:
            raise ValidationError(
                "O desconto total do item não pode ser maior que o valor base do item."
            )

    def calcular_subtotal(self) -> Decimal:
        valor_base = self.quantidade * self.valor_unitario

        desconto_percentual_valor = arredondar(
            valor_base * (self.desconto_percentual / Decimal("100"))
        )
        acrescimo_percentual_valor = arredondar(
            valor_base * (self.acrescimo_percentual / Decimal("100"))
        )

        subtotal = (
            valor_base
            - self.desconto_valor
            - desconto_percentual_valor
            + self.acrescimo_valor
            + acrescimo_percentual_valor
        )

        if subtotal < Decimal("0.00"):
            subtotal = Decimal("0.00")

        return arredondar(subtotal)

    def save(self, *args, **kwargs):
        self.full_clean()
        self.subtotal = self.calcular_subtotal()
        super().save(*args, **kwargs)
