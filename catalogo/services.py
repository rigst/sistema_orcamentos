from decimal import Decimal, InvalidOperation
from io import BytesIO
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from .models import CategoriaItem, ItemCatalogo


XLSX_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


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
                cells = []
                for cell in row.findall("main:c", XLSX_NS):
                    cells.append(_texto_planilha(shared_strings, cell))
                yield cells
    except Exception as exc:
        raise ValueError("Envie um arquivo .xlsx válido.") from exc


def _decimal(valor):
    texto = str(valor or "").strip()
    if not texto:
        return Decimal("0.00")
    normalizado = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalizado)
    except InvalidOperation as exc:
        raise ValueError(f"Valor inválido na importação: {valor}") from exc


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

        if not categoria_nome and not item_nome:
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
            unidade_medida=(unidade or "un").lower(),
            valor_unitario_padrao=_decimal(valor),
            descricao_padrao=descricao,
            observacoes=observacao,
            ativo=True,
        )
        item.save()
        itens_criados += 1

    return categorias_criadas, itens_criados
