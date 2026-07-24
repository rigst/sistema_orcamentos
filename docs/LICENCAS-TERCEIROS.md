# Licenças de terceiros — Sistema de Orçamentos

Gerado por `scripts/licencas_terceiros.py` em 2026-07-24 a partir dos pacotes instalados no venv de produção.
Para regenerar: `./venv/bin/python scripts/licencas_terceiros.py`.

O código deste projeto é licenciado sob **AGPL-3.0** (ver `LICENSE`). As bibliotecas abaixo permanecem sob suas licenças originais.

## Dependências diretas

| Pacote | Versão | Licença |
|---|---|---|
| asgiref | 3.11.1 | BSD License |
| dj-database-url | 3.0.1 | BSD License |
| Django | 6.0.3 | BSD-3-Clause |
| gunicorn | 23.0.0 | MIT License |
| pillow | 12.2.0 | MIT-CMU |
| psycopg | 3.2.12 | LGPL-3.0-only |
| redis | 5.2.1 | MIT License |
| reportlab | 4.4.10 | BSD License |
| sqlparse | 0.5.5 | BSD License |

## Dependências transitivas

| Pacote | Versão | Licença |
|---|---|---|
| charset-normalizer | 3.4.7 | MIT |
| packaging | 26.0 | Apache-2.0 OR BSD-2-Clause |
| psycopg-binary | 3.2.12 | LGPL-3.0-only |
| typing_extensions | 4.15.0 | PSF-2.0 |

## Componentes com licença recíproca (copyleft)

Listados para conferência ao redistribuir o código ou ao combinar com componentes fechados. O uso como biblioteca, sem modificação e sem distribuição do binário, não propaga obrigações de abertura.

| Pacote | Versão | Licença |
|---|---|---|
| psycopg | 3.2.12 | LGPL-3.0-only |
| psycopg-binary | 3.2.12 | LGPL-3.0-only |

## Notas de manutenção

- **Redis**: o servidor em uso é a série 7.0 (BSD-3-Clause). As versões 7.4 a 7.9 passaram a ser RSALv2/SSPL, que não são licenças livres segundo a OSI. Ao atualizar o servidor, reveja esta seção e a página de licenças do site.
