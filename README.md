# Sistema de Orçamentos

Aplicação Django para cadastro de clientes, catálogo de itens, montagem de orçamentos e geração de relatórios em PDF e Excel.

## Requisitos

- Python 3.12
- `venv`

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
```

## Rodando localmente

```bash
source .venv/bin/activate
python manage.py runserver
```

A aplicação ficará disponível em `http://127.0.0.1:8000/`.

## Verificações úteis

Checagem do projeto:

```bash
python manage.py check
```

Testes automatizados:

```bash
python manage.py test
```

## Variáveis de ambiente

O projeto lê automaticamente um arquivo `.env` na raiz.

Para desenvolvimento local, o arquivo `.env.example` já é suficiente como base.

Variáveis principais:

- `DJANGO_ENV`
- `DJANGO_SECRET_KEY`
- `DJANGO_DEBUG`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `SQLITE_TIMEOUT`
- `DJANGO_USE_X_FORWARDED_PROTO`
- `DJANGO_SESSION_COOKIE_SECURE`
- `DJANGO_CSRF_COOKIE_SECURE`
- `DJANGO_SECURE_SSL_REDIRECT`
- `DJANGO_SECURE_HSTS_SECONDS`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`
- `DJANGO_SECURE_HSTS_PRELOAD`
- `DJANGO_LOG_LEVEL`
- `DJANGO_MAX_LOGO_UPLOAD_BYTES`
- `DJANGO_MAX_CATALOGO_UPLOAD_BYTES`
- `DJANGO_VISITANTE_RATE_LIMIT`
- `DJANGO_VISITANTE_RATE_WINDOW_SECONDS`
- `DJANGO_VISITANTE_TTL_HOURS`

Para produção, use como base:

```bash
cp .env.production.example .env
```

Em produção, estes itens são obrigatórios:

- definir `DJANGO_ENV=production`
- definir `DJANGO_SECRET_KEY`
- definir `DJANGO_DEBUG=False`
- ajustar `DJANGO_ALLOWED_HOSTS`
- ajustar `DJANGO_CSRF_TRUSTED_ORIGINS`

## Funcionalidades principais

- autenticação com perfis `admin`, `orcamentista` e `visualizador`
- cadastro de clientes
- cadastro de categorias e itens de catálogo
- criação e edição de orçamentos
- edição dinâmica dos itens do orçamento
- persistência local de rascunho no navegador
- relatórios por orçamento em PDF e Excel
- formatação brasileira de moeda, telefone, CEP e CPF/CNPJ

## CI

O repositório possui workflow em [`.github/workflows/django.yml`](/home/rodrigo/Projetos/sistema_orcamentos/.github/workflows/django.yml) para rodar `check` e `test` no GitHub Actions.
