# Sistema de Orçamentos

Aplicação Django para cadastro de clientes, catálogo de itens, montagem de orçamentos e geração de relatórios em PDF e Excel.

## Requisitos

- Python 3.12
- PostgreSQL 15+ (produção)
- Redis 6+ (produção para cache/rate-limit)

## Instalação local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
```

## Verificações úteis

```bash
python manage.py check
python manage.py test
```

## Variáveis de ambiente

O projeto lê automaticamente o arquivo `.env` na raiz.

Arquivos base:

- desenvolvimento: `.env.example`
- produção: `.env.production.example`

Variáveis de produção mais importantes:

- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY` (segredo)
- `DJANGO_HEALTHZ_TOKEN` (segredo para monitoramento do endpoint `/healthz/`)
- `DJANGO_DEBUG_EXPOSE_MEDIA=False` (evita exposição direta de arquivos em ambiente web)
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`
- `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DATABASE_URL` (segredo: inclui usuário/senha do PostgreSQL)
- `DJANGO_CACHE_BACKEND=redis`
- `DJANGO_REDIS_CACHE_URL` (segredo se tiver senha)
- `DJANGO_USE_X_FORWARDED_PROTO=True`
- `DJANGO_USE_MANIFEST_STATICFILES=True`

## Deploy em VPS com subdomínio

Exemplo alvo: `app.seudominio.com`, com outro site já rodando na mesma VPS.

1. DNS
- Crie registro `A` de `app.seudominio.com` apontando para o IP da VPS.

2. Pacotes no servidor
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip postgresql redis-server nginx certbot python3-certbot-nginx
```

3. Estrutura de pastas
```bash
sudo mkdir -p /var/www/sistema_orcamentos/{current,shared/media}
sudo chown -R $USER:www-data /var/www/sistema_orcamentos
```

4. Código e ambiente virtual
```bash
cd /var/www/sistema_orcamentos/current
git clone <URL_DO_REPOSITORIO> .
python3 -m venv /var/www/sistema_orcamentos/venv
source /var/www/sistema_orcamentos/venv/bin/activate
pip install -r requirements.txt
```

5. Banco PostgreSQL
```bash
sudo -u postgres psql
CREATE DATABASE sistema_orcamentos;
CREATE USER sistema_orcamentos_user WITH PASSWORD 'SENHA_FORTE_AQUI';
GRANT ALL PRIVILEGES ON DATABASE sistema_orcamentos TO sistema_orcamentos_user;
\q
```

6. Arquivo de segredos (`.env`) no servidor
```bash
cp .env.production.example /var/www/sistema_orcamentos/shared/.env
```
Edite `/var/www/sistema_orcamentos/shared/.env` e ajuste:
- `DJANGO_SECRET_KEY` (obrigatório e secreto)
- `DJANGO_HEALTHZ_TOKEN` (obrigatório em produção para proteger `/healthz/`)
- `DJANGO_ALLOWED_HOSTS=app.seudominio.com`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://app.seudominio.com`
- `DATABASE_URL=postgresql://sistema_orcamentos_user:SENHA_FORTE_AQUI@127.0.0.1:5432/sistema_orcamentos`
- `DJANGO_REDIS_CACHE_URL=redis://127.0.0.1:6379/1` (ou com senha)

7. Migrações, estáticos e superusuário
```bash
cd /var/www/sistema_orcamentos/current
source /var/www/sistema_orcamentos/venv/bin/activate
export $(grep -v '^#' /var/www/sistema_orcamentos/shared/.env | xargs)
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

8. Gunicorn (systemd)
```bash
sudo cp deploy/gunicorn.service.example /etc/systemd/system/sistema_orcamentos.service
sudo systemctl daemon-reload
sudo systemctl enable --now sistema_orcamentos.service
sudo systemctl status sistema_orcamentos.service
```

9. Limpeza automática de visitantes expirados
```bash
sudo cp deploy/visitantes-cleanup.service.example /etc/systemd/system/visitantes-cleanup.service
sudo cp deploy/visitantes-cleanup.timer.example /etc/systemd/system/visitantes-cleanup.timer
sudo systemctl daemon-reload
sudo systemctl enable --now visitantes-cleanup.timer
sudo systemctl status visitantes-cleanup.timer
```

10. Nginx para subdomínio
```bash
sudo cp deploy/nginx.sistema_orcamentos.conf.example /etc/nginx/sites-available/sistema_orcamentos
sudo ln -s /etc/nginx/sites-available/sistema_orcamentos /etc/nginx/sites-enabled/sistema_orcamentos
sudo nginx -t
sudo systemctl reload nginx
```

11. SSL/TLS (Let's Encrypt)
```bash
sudo certbot --nginx -d app.seudominio.com
```

12. Validação final
```bash
curl -I -H "X-Healthz-Token: SEU_TOKEN_HEALTHZ" https://app.seudominio.com/healthz/
```
Resposta esperada: HTTP `200`.

## Atualização de versão (deploy contínuo simples)

```bash
cd /var/www/sistema_orcamentos/current
git pull origin main
source /var/www/sistema_orcamentos/venv/bin/activate
pip install -r requirements.txt
export $(grep -v '^#' /var/www/sistema_orcamentos/shared/.env | xargs)
python manage.py migrate
python manage.py collectstatic --noinput
sudo systemctl restart sistema_orcamentos.service
```

## O que não deve ir para o Git / não deve subir para repositório remoto

- `.env` e qualquer `.env.*` de ambiente real (segredos)
- `db.sqlite3`
- `media/` de produção (arquivos de clientes)
- `staticfiles/` gerado por `collectstatic`
- logs e backups

## Segredos

Tratar como segredo:

- `DJANGO_SECRET_KEY`
- `DJANGO_HEALTHZ_TOKEN`
- credenciais do PostgreSQL (`DATABASE_URL`)
- credenciais Redis (se houver senha)
- qualquer token/API key futuro

## Funcionalidades principais

- autenticação com perfis `admin`, `orcamentista`, `visualizador` e `visitante`
- suporte a múltiplas empresas por usuário
- cadastro de clientes
- cadastro de categorias e itens de catálogo
- criação e edição de orçamentos
- relatórios por orçamento em PDF e Excel

## CI

Workflow em [`.github/workflows/django.yml`](/home/rodrigo/Projetos/sistema_orcamentos/.github/workflows/django.yml) executa validações de qualidade e segurança de deploy.

## Licença

Este projeto é distribuído sob a **GNU Affero General Public License v3.0** (ver [LICENSE](LICENSE)). Código-fonte: <https://github.com/rigst/sistema_orcamentos>.
