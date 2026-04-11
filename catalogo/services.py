from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
import unicodedata
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from .models import CategoriaItem, ItemCatalogo


XLSX_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
DUAS_CASAS = Decimal("0.01")
COLUNAS_IMPORTACAO = 6


def _texto_planilha(shared_strings, cell):
    cell_type = cell.attrib.get("t")
    value = cell.findtext("main:v", default="", namespaces=XLSX_NS)
    if cell_type == "s" and value:
        return shared_strings[int(value)]
    if cell_type == "inlineStr":
        return "".join(cell.itertext()).strip()
    return value.strip()


def _carregar_shared_strings(zip_file):
    if "xl/sharedStrings.xml" not in zip_file.namelist():
        return []
    root = ET.fromstring(zip_file.read("xl/sharedStrings.xml"))
    strings = []
    for si in root.findall("main:si", XLSX_NS):
        strings.append("".join(si.itertext()).strip())
    return strings


def _indice_coluna(ref):
    letras = "".join(char for char in str(ref or "") if char.isalpha()).upper()
    indice = 0
    for letra in letras:
        indice = indice * 26 + (ord(letra) - ord("A") + 1)
    return max(indice - 1, 0)


def _linhas_xlsx(arquivo):
    try:
        with ZipFile(BytesIO(arquivo.read())) as zip_file:
            shared_strings = _carregar_shared_strings(zip_file)
            workbook = ET.fromstring(zip_file.read("xl/workbook.xml"))
            rels = ET.fromstring(zip_file.read("xl/_rels/workbook.xml.rels"))
            first_sheet = workbook.find("main:sheets/main:sheet", XLSX_NS)
            if first_sheet is None:
                raise ValueError("A planilha não possui abas.")
            relationship_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            target = None
            for rel in rels:
                if rel.attrib.get("Id") == relationship_id:
                    target = rel.attrib.get("Target")
                    break
            if not target:
                raise ValueError("Não foi possível localizar a primeira aba da planilha.")

            sheet = ET.fromstring(zip_file.read(f"xl/{target}"))
            for row in sheet.findall("main:sheetData/main:row", XLSX_NS):
                cells = [""] * COLUNAS_IMPORTACAO
                for cell in row.findall("main:c", XLSX_NS):
                    indice = _indice_coluna(cell.attrib.get("r"))
                    if indice >= COLUNAS_IMPORTACAO:
                        continue
                    cells[indice] = _texto_planilha(shared_strings, cell)
                yield cells
    except Exception as exc:
        raise ValueError("Envie um arquivo .xlsx válido.") from exc


def _decimal(valor):
    texto = str(valor or "").strip()
    if not texto:
        return Decimal("0.00")
    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto:
        if "." in texto:
            normalizado = texto.replace(".", "").replace(",", ".")
        else:
            normalizado = texto.replace(",", ".")
    else:
        normalizado = texto
    try:
        return Decimal(normalizado).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"Valor inválido na importação: {valor}") from exc


def _slug_unidade(valor):
    texto = unicodedata.normalize("NFKD", str(valor or "").strip())
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return texto.casefold().replace(" ", "").replace(".", "")


def _normalizar_unidade(unidade):
    unidade_original = str(unidade or "").strip()
    unidade_slug = _slug_unidade(unidade_original)

    unidades = {
        "": "un",
        "-": "un",
        "un": "un",
        "unid": "un",
        "unidade": "un",
        "unidades": "un",
        "hr": "hr",
        "hora": "hr",
        "horas": "hr",
        "dia": "dia",
        "diaria": "dia",
        "diarias": "dia",
        "m": "m",
        "metro": "m",
        "metros": "m",
        "m2": "m2",
        "m²": "m2",
        "metroquadrado": "m2",
        "metrosquadrados": "m2",
        "m3": "m3",
        "m³": "m3",
        "metrocubico": "m3",
        "metroscubicos": "m3",
        "kg": "kg",
        "quilo": "kg",
        "quilos": "kg",
        "cx": "cx",
        "caixa": "cx",
        "caixas": "cx",
        "pct": "pct",
        "pacote": "pct",
        "pacotes": "pct",
        "sv": "sv",
        "servico": "sv",
        "servicos": "sv",
        "serviço": "sv",
        "serviços": "sv",
    }
    unidade_normalizada = unidades.get(unidade_slug) or unidades.get(unidade_original.casefold())
    if unidade_normalizada:
        return unidade_normalizada
    raise ValueError(f"Unidade inválida na importação: {unidade_original}")


def importar_catalogo_excel(arquivo, empresa):
    linhas = list(_linhas_xlsx(arquivo))
    if len(linhas) < 2:
        raise ValueError("A planilha precisa ter cabeçalho e ao menos uma linha de dados.")

    categorias_cache = {
        categoria.nome.strip().casefold(): categoria
        for categoria in CategoriaItem.objects.filter(empresa=empresa)
    }
    categorias_criadas = 0
    itens_criados = 0

    for indice, linha in enumerate(linhas[1:], start=2):
        valores = list(linha[:6]) + [""] * max(0, 6 - len(linha))
        categoria_nome, item_nome, valor, unidade, descricao, observacao = [str(v or "").strip() for v in valores[:6]]
        campos_preenchidos = [campo for campo in (categoria_nome, item_nome, valor, unidade, descricao, observacao) if campo]

        if len(campos_preenchidos) <= 1:
            continue
        if not categoria_nome or not item_nome:
            raise ValueError(f"Linha {indice}: informe categoria e item.")

        chave_categoria = categoria_nome.casefold()
        categoria = categorias_cache.get(chave_categoria)
        if categoria is None:
            cor = CategoriaItem.COLOR_SEQUENCE[len(categorias_cache) % len(CategoriaItem.COLOR_SEQUENCE)]
            categoria = CategoriaItem.objects.create(
                empresa=empresa,
                nome=categoria_nome,
                cor=cor,
                ativo=True,
            )
            categorias_cache[chave_categoria] = categoria
            categorias_criadas += 1

        item = ItemCatalogo(
            empresa=empresa,
            categoria=categoria,
            nome=item_nome,
            unidade_medida=_normalizar_unidade(unidade),
            valor_unitario_padrao=_decimal(valor),
            descricao_padrao=descricao,
            observacoes=observacao,
            ativo=True,
        )
        item.save()
        itens_criados += 1

    return categorias_criadas, itens_criados
