from django.urls import path

from .views import (
    configuracao_logo,
    minha_empresa,
    orcamento_exportar_excel,
    orcamento_exportar_memorial_pdf,
    orcamento_exportar_memorial_word,
    orcamento_exportar_pdf,
    orcamento_relatorio_central,
    para_minha_empresa,
)

app_name = "relatorios"

urlpatterns = [
    path("empresa/", minha_empresa, name="minha_empresa"),
    path("configuracoes/<int:pk>/logo/", configuracao_logo, name="configuracao_logo"),
    # Endereços antigos da lista de configurações: hoje é um cadastro só.
    path("configuracoes/", para_minha_empresa, name="configuracao_lista"),
    path("configuracoes/nova/", para_minha_empresa),
    path("configuracoes/<int:pk>/", para_minha_empresa),
    path("configuracoes/<int:pk>/editar/", para_minha_empresa),
    path("orcamentos/<int:pk>/", orcamento_relatorio_central, name="orcamento_central"),
    path("orcamentos/<int:pk>/excel/", orcamento_exportar_excel, name="orcamento_excel"),
    path("orcamentos/<int:pk>/pdf/", orcamento_exportar_pdf, name="orcamento_pdf"),
    path(
        "orcamentos/<int:pk>/memorial-descritivo/pdf/",
        orcamento_exportar_memorial_pdf,
        name="orcamento_memorial_pdf",
    ),
    path(
        "orcamentos/<int:pk>/memorial-descritivo/word/",
        orcamento_exportar_memorial_word,
        name="orcamento_memorial_word",
    ),
]
