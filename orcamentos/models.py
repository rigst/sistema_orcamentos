from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from itertools import groupby
from typing import ClassVar

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models
from django.db.models import Max
from django.utils.timezone import localdate

from core.tenancy import obter_grupo_empresa_padrao

DUAS_CASAS = Decimal("0.01")


def arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


def normalizar_texto_comparacao(valor):
    return " ".join(str(valor or "").split())


# Item que entrou no orçamento sem vir do catálogo (digitado ou sugerido pela
# IA). Rótulo da tela de edição; os documentos do cliente não o mostram.
NAO_REGISTRADO = "Não registrado"


class Orcamento(models.Model):
    STATUS_CHOICES = [
        ("rascunho", "Rascunho"),
        ("em_elaboracao", "Em elaboração"),
        ("enviado", "Enviado"),
        ("aprovado", "Aprovado"),
        ("rejeitado", "Rejeitado"),
        ("cancelado", "Cancelado"),
    ]

    numero = models.CharField(max_length=30)

    # Opcional para não travar a criação: o orçamento nasce sem cliente e ele é
    # definido depois. Tudo que exibe o cliente passa por `cliente_exibicao`.
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="orcamentos",
        null=True,
        blank=True,
    )

    titulo = models.CharField(max_length=255)
    descricao_inicial = models.TextField(blank=True)
    observacoes_gerais = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="rascunho",
    )
    ativo = models.BooleanField(default=True)

    data_emissao = models.DateField()
    validade_em = models.DateField(null=True, blank=True)

    evento_nome = models.CharField(max_length=255, blank=True)
    evento_periodo = models.CharField(max_length=255, blank=True)
    evento_local = models.CharField(max_length=255, blank=True)
    evento_estande = models.CharField(max_length=100, blank=True)
    evento_area = models.CharField(max_length=100, blank=True)
    evento_contato = models.CharField(max_length=255, blank=True)
    evento_telefone = models.CharField(max_length=20, blank=True)
    evento_email = models.CharField(max_length=255, blank=True)

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
    mostrar_descricao_inicial_no_relatorio = models.BooleanField(
        default=True,
        help_text="Se marcado, o PDF do orçamento inclui a descrição inicial.",
    )
    mostrar_observacoes_gerais_no_relatorio = models.BooleanField(
        default=True,
        help_text="Se marcado, o PDF e o memorial incluem as observações gerais.",
    )
    mostrar_rodape_institucional_no_relatorio = models.BooleanField(
        default=True,
        help_text="Se marcado, o PDF do orçamento inclui o rodapé institucional da empresa.",
    )
    mostrar_contatos_evento_no_memorial = models.BooleanField(
        default=True,
        help_text="Se marcado, o memorial inclui os contatos do evento ou projeto.",
    )
    mostrar_financeiro_no_memorial = models.BooleanField(
        default=True,
        help_text="Se marcado, o memorial inclui condições financeiras e dados bancários.",
    )
    mostrar_dados_contratuais_no_memorial = models.BooleanField(
        default=True,
        help_text="Se marcado, o memorial inclui os dados contratuais.",
    )
    mostrar_informacoes_complementares_no_memorial = models.BooleanField(
        default=True,
        help_text="Se marcado, o memorial inclui textos institucionais complementares.",
    )

    condicoes_pagamento = models.TextField(blank=True)
    valor_locacao = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    valor_servico = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    servicos_taxas_inclusos = models.TextField(blank=True)

    contrato_razao_social = models.CharField(max_length=255, blank=True)
    contrato_cnpj = models.CharField(max_length=20, blank=True)
    contrato_endereco = models.CharField(max_length=255, blank=True)
    contrato_cidade = models.CharField(max_length=100, blank=True)
    contrato_cep = models.CharField(max_length=10, blank=True)
    contrato_responsavel_nome = models.CharField(max_length=255, blank=True)
    contrato_responsavel_documento = models.CharField(max_length=30, blank=True)
    contrato_cargo_funcao = models.CharField(max_length=255, blank=True)
    contrato_telefone = models.CharField(max_length=20, blank=True)
    contrato_email = models.EmailField(blank=True)
    contrato_inscricao_estadual = models.CharField(max_length=30, blank=True)

    configuracao_empresa = models.ForeignKey(
        "relatorios.ConfiguracaoEmpresa",
        on_delete=models.PROTECT,
        related_name="orcamentos",
        null=True,
        blank=True,
    )

    empresa = models.ForeignKey(
        "auth.Group",
        on_delete=models.PROTECT,
        related_name="orcamentos",
        null=True,
        blank=True,
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
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "numero"], name="orcamento_empresa_numero_uniq"
            ),
        ]

    # Carona de escopo entre save() e gerar_proximo_numero(), que é classmethod
    # e não recebe a instância. Anotado porque só era criado por atribuição
    # dentro do save, e o mypy não enxerga atributo que nasce assim.
    _empresa_numero_context: ClassVar[Group | None] = None

    SEM_CLIENTE = "Cliente a definir"
    TITULO_GENERICO = "Novo orçamento"

    def __str__(self):
        return f"{self.numero} - {self.cliente_exibicao}"

    def save(self, *args, **kwargs):
        if self.data_emissao is None:
            self.data_emissao = localdate()
        if self.empresa_id is None:
            if self.criado_por_id and self.criado_por.groups.exists():
                self.empresa = self.criado_por.groups.order_by("name", "id").first()
            else:
                self.empresa = obter_grupo_empresa_padrao()
        if self.configuracao_empresa_id is None and self.empresa_id:
            from relatorios.models import ConfiguracaoEmpresa

            self.configuracao_empresa = ConfiguracaoEmpresa.da_empresa(self.empresa)
        if self.pk is None:
            self.aplicar_padroes_da_empresa()
        if self._cliente_mudou():
            # Só preenche campo contratual vazio: o que foi digitado fica.
            self.preencher_contrato_do_cliente()
        max_tentativas = 5 if not self.pk else 1
        for tentativa in range(max_tentativas):
            type(self)._empresa_numero_context = self.empresa
            try:
                self.definir_numero_automatico()
                self.full_clean()
                super().save(*args, **kwargs)
                return
            except IntegrityError as exc:
                if self.pk or tentativa == max_tentativas - 1:
                    raise
                if "orcamento_empresa_numero_uniq" not in str(
                    exc
                ) and "UNIQUE constraint failed" not in str(exc):
                    raise
            finally:
                type(self)._empresa_numero_context = None

    def _cliente_mudou(self) -> bool:
        if not self.cliente_id:
            return False
        if self.pk is None:
            return True
        anterior = (
            type(self).objects.filter(pk=self.pk).values_list("cliente_id", flat=True).first()
        )
        return anterior != self.cliente_id

    def aplicar_padroes_da_empresa(self):
        """Orçamento novo herda validade e condições comerciais do cadastro da
        empresa. Só preenche o que veio vazio."""
        configuracao = self.configuracao_empresa if self.configuracao_empresa_id else None
        if configuracao is None:
            return
        if self.validade_em is None:
            self.validade_em = configuracao.validade_a_partir(self.data_emissao)
        if not (self.condicoes_pagamento or "").strip():
            self.condicoes_pagamento = configuracao.condicoes_pagamento_padrao
        if not (self.servicos_taxas_inclusos or "").strip():
            self.servicos_taxas_inclusos = configuracao.servicos_taxas_inclusos_padrao

    def dados_contratuais_do_cliente(self) -> dict:
        """Os campos contratuais como o cadastro do cliente os preencheria."""
        cliente = self.cliente if self.cliente_id else None
        if cliente is None:
            return {}
        partes = (cliente.logradouro, cliente.numero, cliente.complemento, cliente.bairro)
        cidade = (cliente.cidade, cliente.estado)
        return {
            "contrato_razao_social": cliente.nome_razao_social,
            "contrato_cnpj": cliente.cpf_cnpj,
            "contrato_endereco": ", ".join(p.strip() for p in partes if (p or "").strip()),
            "contrato_cidade": "/".join(p.strip() for p in cidade if (p or "").strip()),
            "contrato_cep": cliente.cep,
            "contrato_responsavel_nome": cliente.contato_responsavel,
            "contrato_telefone": cliente.telefone or cliente.celular,
            "contrato_email": cliente.email,
        }

    def preencher_contrato_do_cliente(self, *, sobrescrever=False) -> list[str]:
        """Copia os dados do cliente para os campos contratuais. Por padrão só
        preenche os vazios, o que nunca perde algo digitado. Devolve os campos
        alterados (sem salvar)."""
        alterados = []
        for campo, valor in self.dados_contratuais_do_cliente().items():
            limite = getattr(self._meta.get_field(campo), "max_length", None)
            valor = (valor or "").strip()[:limite]
            atual = (getattr(self, campo) or "").strip()
            if not valor or valor == atual or (atual and not sobrescrever):
                continue
            setattr(self, campo, valor)
            alterados.append(campo)
        return alterados

    @property
    def cliente_exibicao(self) -> str:
        return str(self.cliente) if self.cliente_id else self.SEM_CLIENTE

    @property
    def titulo_e_generico(self) -> bool:
        return not (self.titulo or "").strip() or self.titulo == self.TITULO_GENERICO

    @classmethod
    def gerar_proximo_numero(cls, ano: int) -> str:
        prefixo = f"ORC-{ano}-"
        queryset = cls.objects.filter(numero__startswith=prefixo)
        if getattr(cls, "_empresa_numero_context", None) is not None:
            queryset = queryset.filter(empresa=cls._empresa_numero_context)
        ultimo_numero = queryset.aggregate(max_numero=Max("numero"))["max_numero"]
        sequencial = 1
        if ultimo_numero:
            try:
                sequencial = int(str(ultimo_numero).rsplit("-", 1)[-1]) + 1
            except (TypeError, ValueError):
                sequencial = 1
        return f"{prefixo}{sequencial:04d}"

    def definir_numero_automatico(self):
        if self.pk:
            numero_original = (
                type(self).objects.filter(pk=self.pk).values_list("numero", flat=True).first()
            )
            if numero_original:
                self.numero = numero_original
                return

        data_referencia = self.data_emissao
        if isinstance(data_referencia, str):
            data_referencia = date.fromisoformat(data_referencia)
        ano = data_referencia.year if data_referencia else date.today().year
        self.numero = self.gerar_proximo_numero(ano)

    def clean(self):
        if self.validade_em and self.validade_em < self.data_emissao:
            raise ValidationError(
                {"validade_em": "A validade não pode ser anterior à data de emissão."}
            )
        configuracao = self.configuracao_empresa if self.configuracao_empresa_id else None
        if configuracao and self.empresa_id:
            if configuracao.empresa_id != self.empresa_id:
                raise ValidationError(
                    {
                        "configuracao_empresa": "Selecione uma configuração da mesma empresa do orçamento."
                    }
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

    @property
    def valor_desconto_percentual_global(self) -> Decimal:
        return arredondar(self.subtotal_itens * (self.desconto_global_percentual / Decimal("100")))

    @property
    def valor_acrescimo_percentual_global(self) -> Decimal:
        return arredondar(self.subtotal_itens * (self.acrescimo_global_percentual / Decimal("100")))

    def recalcular_totais(self, salvar: bool = True):
        self.subtotal_itens = self.calcular_subtotal_itens()
        self.total_final = self.calcular_total_final()

        if salvar:
            self.save(update_fields=["subtotal_itens", "total_final", "atualizado_em"])

    def subtotais_por_categoria(self, rotulo_sem_catalogo: str | None = None):
        """Subtotal por categoria do catálogo, na ordem do nome da categoria.

        `rotulo_sem_catalogo`: no editor, os itens que não vieram do catálogo
        ficam num grupo à parte com esse nome ("Não registrado"), separado dos
        itens de catálogo sem categoria. Sem ele (relatórios para o cliente),
        os dois casos caem juntos em "Sem categoria", como sempre foi.
        """
        itens = list(self.itens.select_related("item_catalogo__categoria").all())

        def categoria_do_item(item):
            catalogo = item.item_catalogo if item.item_catalogo_id else None
            categoria = catalogo.categoria if catalogo and catalogo.categoria_id else None
            if categoria is not None:
                return categoria.pk, categoria.nome, categoria.cor
            if catalogo is None and rotulo_sem_catalogo:
                return None, rotulo_sem_catalogo, "#94A3B8"
            return None, "Sem categoria", "#CBD5E1"

        # Grupos com categoria primeiro (por nome); os sem categoria no fim.
        itens.sort(
            key=lambda i: (categoria_do_item(i)[0] is None, categoria_do_item(i)[1], i.ordem, i.pk)
        )

        total = sum((item.subtotal for item in itens), Decimal("0.00"))
        grupos = []
        for chave, itens_grupo in groupby(itens, key=categoria_do_item):
            itens_lista = list(itens_grupo)
            subtotal = arredondar(sum((item.subtotal for item in itens_lista), Decimal("0.00")))
            grupos.append(
                {
                    "categoria_id": chave[0],
                    "categoria_nome": chave[1],
                    "categoria_cor": chave[2],
                    "subtotal": subtotal,
                    "quantidade_itens": len(itens_lista),
                    "percentual": arredondar(subtotal * 100 / total) if total else Decimal("0.00"),
                    "itens": itens_lista,
                }
            )
        return grupos


class ItemOrcamento(models.Model):
    UNIDADE_CHOICES = [
        ("un", "Unidade"),
        ("hr", "Hora"),
        ("dia", "Diária"),
        ("m", "m"),
        ("m2", "m2"),
        ("m3", "m3"),
        ("kg", "Quilo"),
        ("cx", "Caixa"),
        ("pct", "Pacote"),
        ("sv", "Serviço"),
        ("-", "-"),
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

    def save(self, *args, **kwargs):
        self.definir_codigo_automatico()
        self.full_clean()
        self.subtotal = self.calcular_subtotal()
        super().save(*args, **kwargs)

    # Anexado pelo formulário de pré-visualização para o template ler, e não
    # persistido: o card do item precisa da lista de divergências já calculada.
    divergencias_catalogo: list[str] | None = None

    def campos_divergentes_catalogo(self):
        catalogo = self.item_catalogo if self.item_catalogo_id else None
        if catalogo is None:
            return []

        divergencias = []
        if normalizar_texto_comparacao(self.nome) != normalizar_texto_comparacao(catalogo.nome):
            divergencias.append("nome")
        if (self.unidade_medida or "").strip() != (catalogo.unidade_medida or "").strip():
            divergencias.append("unidade")
        if arredondar(self.valor_unitario or Decimal("0.00")) != arredondar(
            catalogo.valor_unitario_padrao or Decimal("0.00")
        ):
            divergencias.append("valor")
        return divergencias

    @property
    def diverge_catalogo(self):
        return bool(self.campos_divergentes_catalogo())

    def gerar_codigo_item(self) -> str:
        prefixo = f"{self.orcamento.numero}-ITEM-"
        codigos = (
            type(self)
            .objects.filter(orcamento=self.orcamento)
            .exclude(pk=self.pk)
            .values_list("codigo_item", flat=True)
        )
        maior = 0
        for codigo in codigos:
            if not codigo or not str(codigo).startswith(prefixo):
                continue
            try:
                maior = max(maior, int(str(codigo).rsplit("-", 1)[-1]))
            except (TypeError, ValueError):
                continue
        return f"{prefixo}{maior + 1:03d}"

    def definir_codigo_automatico(self):
        if self.pk:
            codigo_original = (
                type(self).objects.filter(pk=self.pk).values_list("codigo_item", flat=True).first()
            )
            if codigo_original:
                self.codigo_item = codigo_original
                return
        self.codigo_item = self.gerar_codigo_item()

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


# Registra o modelo de versões (vive em módulo próprio para não inchar este).
from .models_versoes import VersaoOrcamento  # noqa: E402, F401
