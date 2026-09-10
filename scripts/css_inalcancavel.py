#!/usr/bin/env python3
"""Acha regras de CSS que a cascata torna inalcançáveis, e prova que remover é no-op.

Uma regra entra na lista só quando TODAS as suas declarações são sobrescritas
adiante por um seletor **idêntico**, no **mesmo contexto** de at-rule, com
`!important` igual ou maior. Nesse caso ela não vence de ninguém: todo elemento
que ela casa também casa a posterior, com a mesma especificidade, e a posterior
vem depois.

Fica de fora de propósito, por ser onde o erro moraria: seletor com vírgula,
contexto de media diferente, atalho contra longhand (`margin` depois de
`margin-top` é sobrescrita de fato, mas comparar só nomes iguais mantém a
análise conservadora) e `!important` anterior sob posterior sem `!important`.

A análise usa o `tinycss2`, e não um scanner próprio: a primeira versão era
artesanal e o teste pegou dois defeitos nela — perdia regra dentro de
`@media` e confundia `;` dentro de string (`content: "; }"`). Para editar CSS
de produção isso não serve.

O recorte para remoção é conferido antes de sair: o texto extraído tem de
voltar a ser exatamente uma regra, com o mesmo seletor e as mesmas
declarações. E, no fim, a cascata inteira é comparada antes e depois.
"""
import re, sys, pathlib, collections
import tinycss2


def declaracoes(conteudo):
    d = {}
    for no in tinycss2.parse_declaration_list(conteudo, skip_whitespace=True, skip_comments=True):
        if no.type == 'declaration':
            d[no.lower_name] = (tinycss2.serialize(no.value).strip(), no.important)
    return d


def coletar(nos, ctx, saida):
    for no in nos:
        if no.type == 'qualified-rule':
            saida.append({
                'ctx': ctx,
                'sel': re.sub(r'\s+', ' ', tinycss2.serialize(no.prelude)).strip(),
                'decls': declaracoes(no.content),
                'linha': no.source_line, 'coluna': no.source_column,
            })
        elif no.type == 'at-rule' and no.content is not None:
            nome = (no.lower_at_keyword or '')
            if nome in ('media', 'supports', 'layer', 'container'):
                prelu = re.sub(r'\s+', ' ', tinycss2.serialize(no.prelude)).strip()
                coletar(tinycss2.parse_rule_list(no.content, skip_whitespace=True,
                                                 skip_comments=True),
                        ctx + (f'@{nome} {prelu}',), saida)


def regras(texto):
    saida = []
    coletar(tinycss2.parse_stylesheet(texto, skip_whitespace=True, skip_comments=True),
            (), saida)
    return saida


def mortas(rs):
    por_chave = collections.defaultdict(list)
    for i, r in enumerate(rs):
        por_chave[(r['ctx'], r['sel'])].append(i)
    alvo = []
    for (_ctx, sel), idxs in por_chave.items():
        if ',' in sel or len(idxs) < 2 or not sel:
            continue
        for pos, i in enumerate(idxs[:-1]):
            decls = rs[i]['decls']
            if not decls:
                continue
            posteriores = idxs[pos + 1:]
            def coberta(nome, imp):
                return any((lambda d: d and (d[1] or not imp))(rs[j]['decls'].get(nome))
                           for j in posteriores)
            if all(coberta(n, v[1]) for n, v in decls.items()):
                alvo.append(i)
    return sorted(set(alvo))


def cascata(rs):
    venc = {}
    for r in rs:
        for nome, (valor, imp) in r['decls'].items():
            ch = (r['ctx'], r['sel'], nome)
            ant = venc.get(ch)
            if ant is None or imp or not ant[1]:
                venc[ch] = (valor, imp)
    return venc


def deslocamento(texto, linha, coluna):
    linhas = texto.split('\n')
    return sum(len(l) + 1 for l in linhas[:linha - 1]) + (coluna - 1)


def fim_da_regra(texto, ini):
    """Índice logo após o `}` que fecha a regra. Respeita string e comentário."""
    i, n = ini, len(texto)
    while i < n and texto[i] != '{':
        if texto[i] == '/' and texto[i+1:i+2] == '*':
            f = texto.find('*/', i + 2); i = n if f < 0 else f + 2; continue
        if texto[i] in '"\'':
            a, j = texto[i], i + 1
            while j < n and texto[j] != a:
                j += 2 if texto[j] == '\\' else 1
            i = j + 1; continue
        i += 1
    prof, i = 1, i + 1
    while i < n and prof:
        c = texto[i]
        if c == '/' and texto[i+1:i+2] == '*':
            f = texto.find('*/', i + 2); i = n if f < 0 else f + 2; continue
        if c in '"\'':
            a, j = c, i + 1
            while j < n and texto[j] != a:
                j += 2 if texto[j] == '\\' else 1
            i = j + 1; continue
        prof += (c == '{') - (c == '}')
        i += 1
    return i


def recorte_confere(trecho, r):
    """O texto a remover tem de ser exatamente aquela regra."""
    nos = [n for n in tinycss2.parse_stylesheet(trecho, skip_whitespace=True, skip_comments=True)]
    if len(nos) != 1 or nos[0].type != 'qualified-rule':
        return False
    sel = re.sub(r'\s+', ' ', tinycss2.serialize(nos[0].prelude)).strip()
    return sel == r['sel'] and declaracoes(nos[0].content) == r['decls']


if __name__ == '__main__':
    arq = pathlib.Path(sys.argv[1])
    texto = arq.read_text(encoding='utf-8')
    rs = regras(texto)
    mortos = mortas(rs)
    print(f"{arq}: {len(rs)} regras, {len(mortos)} inalcançáveis")
    for i in mortos[:60]:
        r = rs[i]
        print(f"  linha {r['linha']:5}  {' > '.join(r['ctx']) or 'topo':26} "
              f"{r['sel'][:44]:46} {len(r['decls'])} decl")

    if len(sys.argv) > 2 and sys.argv[2] == '--aplicar':
        recortes = []
        for i in mortos:
            r = rs[i]
            a = deslocamento(texto, r['linha'], r['coluna'])
            b = fim_da_regra(texto, a)
            if not recorte_confere(texto[a:b], r):
                print(f"PULADO (recorte não confere): linha {r['linha']} {r['sel'][:40]}")
                continue
            recortes.append((a, b))
        novo = texto
        for a, b in sorted(recortes, reverse=True):
            while a > 0 and novo[a-1] in ' \t':
                a -= 1
            while b < len(novo) and novo[b] in ' \t':
                b += 1
            if b < len(novo) and novo[b] == '\n':
                b += 1
            novo = novo[:a] + novo[b:]
        # At-rule que ficou sem conteúdo sai junto: `@media screen {}` é
        # inofensivo, mas o `block-no-empty` do Stylelint o acusaria — a
        # limpeza não pode criar achado novo.
        anterior = None
        while anterior != novo:
            anterior = novo
            novo = re.sub(r'^[ \t]*@[^{;]*\{\s*\}[ \t]*\n?', '', novo, flags=re.M)
        novo = re.sub(r'\n{3,}', '\n\n', novo)
        antes, depois = cascata(rs), cascata(regras(novo))
        if antes != depois:
            dif = [k for k in set(antes) | set(depois) if antes.get(k) != depois.get(k)]
            print(f"ABORTADO: a cascata mudou em {len(dif)} ponto(s)")
            for k in dif[:5]:
                print("   ", k, antes.get(k), '->', depois.get(k))
            sys.exit(1)
        arq.write_text(novo, encoding='utf-8')
        print(f"aplicado: {len(recortes)} regras removidas, cascata idêntica em "
              f"{len(antes)} pontos, {len(texto.splitlines()) - len(novo.splitlines())} linhas a menos")
