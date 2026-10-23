"""O que a IA leu do edital vira dados do orçamento.

Duas regras valem para tudo aqui: o que o usuário já preencheu nunca é
sobrescrito, e o cliente é sempre procurado ou criado dentro da empresa dona
do orçamento.
"""

from __future__ import annotations

from clientes.models import Cliente
from core.formatting import formatar_cpf_cnpj_br


def _cortar(texto, limite):
    return " ".join(str(texto or "").split())[:limite]


CAMPOS_EVENTO = {
    "evento_nome": 255,
    "evento_local": 255,
    "evento_periodo": 255,
    "evento_area": 100,
}


CAMPOS_CONTRATO = {
    "contrato_razao_social": ("contratante_nome", 255),
    "contrato_endereco": ("contratante_endereco", 255),
    "contrato_cidade": ("contratante_cidade", 100),
}


def _so_digitos(valor) -> str:
    return "".join(c for c in str(valor or "") if c.isdigit())


def _cnpj_formatado(valor) -> str:
    digitos = _so_digitos(valor)
    return formatar_cpf_cnpj_br(digitos) if len(digitos) in (11, 14) else ""


def _preencher_vazios(orcamento, dados_orcamento):
    """Evento, descrição e dados contratuais. Só preenche campo vazio: o que
    o usuário já digitou não é sobrescrito."""
    alterados = []
    for campo, limite in CAMPOS_EVENTO.items():
        valor = _cortar(dados_orcamento.get(campo), limite)
        if valor and not getattr(orcamento, campo):
            setattr(orcamento, campo, valor)
            alterados.append(campo)
    for campo, (origem, limite) in CAMPOS_CONTRATO.items():
        valor = _cortar(dados_orcamento.get(origem), limite)
        if valor and not getattr(orcamento, campo):
            setattr(orcamento, campo, valor)
            alterados.append(campo)
    cnpj = _cnpj_formatado(dados_orcamento.get("contratante_cnpj"))
    if cnpj and not orcamento.contrato_cnpj:
        orcamento.contrato_cnpj = cnpj
        alterados.append("contrato_cnpj")
    descricao = str(dados_orcamento.get("descricao_inicial") or "").strip()
    if descricao and not orcamento.descricao_inicial.strip():
        orcamento.descricao_inicial = descricao
        alterados.append("descricao_inicial")
    return alterados


def _cliente_do_contratante(empresa, dados_orcamento):
    """(cliente, criado). Procura pelo CNPJ e depois pelo nome, sempre dentro
    da empresa. Sem nenhum dos dois, cadastra o contratante como cliente novo."""
    nome = _cortar(dados_orcamento.get("contratante_nome"), 255)
    if not nome:
        return None, False
    clientes = Cliente.objects.filter(empresa=empresa)
    digitos = _so_digitos(dados_orcamento.get("contratante_cnpj"))
    if len(digitos) in (11, 14):
        for cliente in clientes.exclude(cpf_cnpj=""):
            if _so_digitos(cliente.cpf_cnpj) == digitos:
                return cliente, False
    existente = clientes.filter(nome_razao_social__iexact=nome).first()
    if existente is not None:
        return existente, False
    cidade_uf = str(dados_orcamento.get("contratante_cidade") or "")
    cidade, _, uf = cidade_uf.rpartition("/")
    if not cidade:
        cidade, uf = uf, ""
    cliente = Cliente.objects.create(
        empresa=empresa,
        tipo_pessoa="PF" if len(digitos) == 11 else "PJ",
        nome_razao_social=nome,
        cpf_cnpj=_cnpj_formatado(digitos),
        logradouro=_cortar(dados_orcamento.get("contratante_endereco"), 255),
        cidade=_cortar(cidade, 100),
        estado=uf.strip().upper()[:2] if len(uf.strip()) == 2 else "",
        observacoes="Cadastrado automaticamente a partir de um memorial descritivo.",
    )
    return cliente, True


def preencher_dados_gerais(orcamento, dados_orcamento, empresa):
    """Título (se ainda for o genérico), cliente (se ainda não tiver) e os
    campos vazios. Devolve (campos alterados, resumo para a tela)."""
    alterados = _preencher_vazios(orcamento, dados_orcamento)
    resumo = {}
    titulo = _cortar(dados_orcamento.get("titulo"), 255)
    if titulo and orcamento.titulo_e_generico:
        orcamento.titulo = titulo
        alterados.append("titulo")
    if not orcamento.cliente_id:
        cliente, criado = _cliente_do_contratante(empresa, dados_orcamento)
        if cliente is not None:
            orcamento.cliente = cliente
            alterados.append("cliente")
            resumo = {"cliente_id": cliente.pk, "cliente_nome": str(cliente), "criado": criado}
    return alterados, resumo
