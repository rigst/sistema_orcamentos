"""Leitura do memorial enviado pelo usuário.

PDF não é convertido aqui: vai inteiro para a Claude como bloco `document`, que
lê tabela, coluna dupla e até PDF escaneado melhor do que qualquer extrator de
texto que caberia neste app. DOCX e TXT viram texto puro. O arquivo nunca é
gravado em disco nem no banco.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from django.conf import settings

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

MAX_DOCX_ENTRADAS = 500
MAX_DOCX_RAZAO_COMPRESSAO = 100
MAX_DOCX_DESCOMPACTADO_BYTES = 30 * 1024 * 1024

EXTENSOES_ACEITAS = (".pdf", ".docx", ".txt", ".md")


class MemorialInvalido(ValueError):
    """Arquivo ou texto que não dá para mandar à IA. A mensagem vai à tela."""


@dataclass(frozen=True)
class Memorial:
    """O conteúdo pronto para a chamada: ou um PDF, ou texto."""

    nome: str
    pdf_base64: str = ""
    texto: str = ""

    def blocos_conteudo(self):
        if self.pdf_base64:
            return [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": self.pdf_base64,
                    },
                    "title": self.nome or "memorial.pdf",
                }
            ]
        return [{"type": "text", "text": f"<memorial>\n{self.texto}\n</memorial>"}]


def _limite_bytes():
    return int(getattr(settings, "MEMORIAL_IA_MAX_UPLOAD_BYTES", 15 * 1024 * 1024))


def _limite_caracteres():
    return int(getattr(settings, "MEMORIAL_IA_MAX_CARACTERES", 300_000))


def _validar_zip(zip_file):
    infos = zip_file.infolist()
    if len(infos) > MAX_DOCX_ENTRADAS:
        raise MemorialInvalido("O .docx tem entradas internas demais.")
    total = 0
    for info in infos:
        total += info.file_size
        if info.compress_size and info.file_size / info.compress_size > MAX_DOCX_RAZAO_COMPRESSAO:
            raise MemorialInvalido("O .docx tem compressão suspeita e foi recusado.")
    if total > MAX_DOCX_DESCOMPACTADO_BYTES:
        raise MemorialInvalido("O .docx descompactado passa do tamanho permitido.")


def _texto_paragrafo(paragrafo):
    return "".join(no.text or "" for no in paragrafo.iter(f"{W_NS}t")).strip()


def _texto_docx(conteudo: bytes) -> str:
    """Parágrafos e tabelas na ordem do documento. Cada linha de tabela vira
    `célula | célula`, que é o formato que a IA lê melhor como planilha."""
    try:
        with ZipFile(BytesIO(conteudo)) as zip_file:
            _validar_zip(zip_file)
            if "word/document.xml" not in zip_file.namelist():
                raise MemorialInvalido("O arquivo não parece um .docx válido.")
            raiz = ET.fromstring(zip_file.read("word/document.xml"))
    except (BadZipFile, ET.ParseError) as exc:
        raise MemorialInvalido("Não consegui abrir o .docx. Ele está corrompido?") from exc

    corpo = raiz.find(f"{W_NS}body")
    if corpo is None:
        return ""
    linhas = []
    for bloco in corpo:
        if bloco.tag == f"{W_NS}p":
            texto = _texto_paragrafo(bloco)
            if texto:
                linhas.append(texto)
        elif bloco.tag == f"{W_NS}tbl":
            for linha in bloco.iter(f"{W_NS}tr"):
                celulas = [
                    " ".join(_texto_paragrafo(p) for p in celula.iter(f"{W_NS}p")).strip()
                    for celula in linha.iter(f"{W_NS}tc")
                ]
                if any(celulas):
                    linhas.append(" | ".join(celulas))
            linhas.append("")
    return "\n".join(linhas).strip()


def _texto_simples(conteudo: bytes) -> str:
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return conteudo.decode(codificacao)
        except UnicodeDecodeError:
            continue
    raise MemorialInvalido("Não consegui ler a codificação do arquivo de texto.")


def _validar_texto(texto: str) -> str:
    texto = (texto or "").strip()
    if len(texto) < 40:
        raise MemorialInvalido("O memorial está vazio ou curto demais para gerar um orçamento.")
    if len(texto) > _limite_caracteres():
        raise MemorialInvalido(
            "O memorial passa do tamanho que a IA consegue ler de uma vez. "
            "Envie só a parte do memorial descritivo, sem os anexos do edital."
        )
    return texto


def ler_memorial(arquivo=None, texto_colado: str = "") -> Memorial:
    """Recebe o UploadedFile do formulário (ou o texto colado) e devolve o
    conteúdo pronto. Levanta MemorialInvalido com mensagem para o usuário."""
    if arquivo is None:
        return Memorial(nome="texto colado", texto=_validar_texto(texto_colado))

    nome = (getattr(arquivo, "name", "") or "memorial").strip()
    extensao = nome.lower().rsplit(".", 1)[-1] if "." in nome else ""
    if f".{extensao}" not in EXTENSOES_ACEITAS:
        raise MemorialInvalido("Formato não aceito. Envie PDF, DOCX ou TXT.")

    conteudo = arquivo.read(_limite_bytes() + 1)
    if len(conteudo) > _limite_bytes():
        limite_mb = _limite_bytes() // (1024 * 1024)
        raise MemorialInvalido(f"O arquivo passa de {limite_mb} MB.")
    if not conteudo:
        raise MemorialInvalido("O arquivo está vazio.")

    if extensao == "pdf":
        if not conteudo.startswith(b"%PDF"):
            raise MemorialInvalido("O arquivo não parece um PDF válido.")
        return Memorial(nome=nome, pdf_base64=base64.b64encode(conteudo).decode("ascii"))
    if extensao == "docx":
        return Memorial(nome=nome, texto=_validar_texto(_texto_docx(conteudo)))
    return Memorial(nome=nome, texto=_validar_texto(_texto_simples(conteudo)))
