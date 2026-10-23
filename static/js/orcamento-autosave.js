/*
 * Salvamento automático do orçamento, com desfazer e refazer.
 *
 * - Campos do formulário principal (título, cliente, abas Evento, Comercial
 *   e Contrato, desconto e acréscimo no total): salvam sozinhos ~800 ms depois
 *   de parar de digitar, ou na hora ao sair do campo.
 * - As ações de item (editar na linha, adicionar, mover, duplicar, excluir)
 *   já salvam no servidor e avisam por `orcamento:salvo`; aqui só se atualizam
 *   o status e os botões.
 * - Desfazer/refazer (botões ou Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y fora de campo
 *   de texto) restauram uma versão no servidor e recarregam a página na mesma
 *   aba e rolagem: assim tudo que está na tela vem da versão restaurada.
 */
(() => {
  "use strict";

  const barra = document.querySelector("[data-autosave]");
  const form = document.querySelector("form[data-autosave-form]");
  if (!barra || !form) return;

  const ESPERA_MS = 800;
  const statusEl = barra.querySelector("[data-autosave-status]");
  const btnDesfazer = barra.querySelector("[data-desfazer]");
  const btnRefazer = barra.querySelector("[data-refazer]");
  const concorrencia = form.querySelector("[name='concorrencia_atualizado_em']");
  const CHAVE_POSICAO = `orc-posicao:${location.pathname}`;

  let timer = null;
  let salvando = false;
  let pendente = false;
  let ultimoEnviado = null;

  const csrf = () => form.querySelector("input[name='csrfmiddlewaretoken']")?.value || "";

  const mostrar = (texto, tipo) => {
    statusEl.textContent = texto;
    statusEl.dataset.tipo = tipo;
  };

  const rotulo = (base, descricao, atalho) =>
    `${base}${descricao ? `: ${descricao}` : ""} (${atalho})`;

  const aplicarHistorico = (historico) => {
    if (!historico) return;
    btnDesfazer.disabled = !historico.pode_desfazer;
    btnRefazer.disabled = !historico.pode_refazer;
    btnDesfazer.title = rotulo("Desfazer", historico.desfazer_rotulo, "Ctrl+Z");
    btnRefazer.title = rotulo("Refazer", historico.refazer_rotulo, "Ctrl+Shift+Z");
  };

  const aplicarResposta = (dados) => {
    if (dados.concorrencia && concorrencia) concorrencia.value = dados.concorrencia;
    aplicarHistorico(dados.historico);
    const totais = document.getElementById("totais-card-region");
    if (totais && dados.totais_html !== undefined) totais.innerHTML = dados.totais_html;
  };

  const limparErros = () => {
    form.querySelectorAll("[data-erro-autosave]").forEach((el) => el.remove());
    form.querySelectorAll("[aria-invalid='true']").forEach((el) => el.removeAttribute("aria-invalid"));
  };

  const mostrarErros = (erros) => {
    limparErros();
    let primeiro = null;
    Object.entries(erros || {}).forEach(([nome, mensagens]) => {
      const campo = document.querySelector(`[name='${CSS.escape(nome)}'][form='orcamento-main-form'], #orcamento-main-form [name='${CSS.escape(nome)}']`);
      const aviso = document.createElement("p");
      aviso.className = "ds-help ds-help--error";
      aviso.dataset.erroAutosave = "1";
      aviso.textContent = mensagens.join(" ");
      if (campo) {
        campo.setAttribute("aria-invalid", "true");
        campo.insertAdjacentElement("afterend", aviso);
        primeiro = primeiro || campo;
      } else {
        form.prepend(aviso);
      }
    });
    return primeiro;
  };

  const dadosDoForm = () => {
    const dados = new FormData(form);
    // Desconto e acréscimo ficam fora do <form>, ligados pelo atributo `form`.
    document.querySelectorAll("[form='orcamento-main-form'][name]").forEach((campo) => {
      if (!form.contains(campo)) dados.set(campo.name, campo.value);
    });
    return dados;
  };

  const assinatura = (dados) =>
    JSON.stringify([...dados.entries()].filter(([k]) => k !== "csrfmiddlewaretoken" && k !== "concorrencia_atualizado_em"));

  const salvar = async () => {
    clearTimeout(timer);
    if (salvando) {
      pendente = true;
      return;
    }
    const dados = dadosDoForm();
    const marca = assinatura(dados);
    if (marca === ultimoEnviado) return;

    salvando = true;
    mostrar("Salvando…", "salvando");
    try {
      const resposta = await fetch(barra.dataset.urlSalvar, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() },
        body: dados,
        credentials: "same-origin",
      });
      const corpo = await resposta.json().catch(() => ({}));
      if (resposta.status === 400 && corpo.erros) {
        const naoCampo = corpo.erros.__all__;
        mostrarErros(corpo.erros);
        mostrar(naoCampo ? naoCampo.join(" ") : "Revise o campo destacado", "erro");
        return;
      }
      if (!resposta.ok) throw new Error();
      ultimoEnviado = marca;
      limparErros();
      aplicarResposta(corpo);
      mostrar("Tudo salvo", "ok");
    } catch (error_) {
      mostrar("Sem conexão. Vou tentar de novo.", "erro");
      timer = setTimeout(() => void salvar(), 4000);
    } finally {
      salvando = false;
      if (pendente) {
        pendente = false;
        void salvar();
      }
    }
  };

  const agendar = () => {
    mostrar("Alterações não salvas", "pendente");
    clearTimeout(timer);
    timer = setTimeout(() => void salvar(), ESPERA_MS);
  };

  const ehDoForm = (alvo) =>
    alvo instanceof Element &&
    alvo.name &&
    (form.contains(alvo) || alvo.getAttribute("form") === "orcamento-main-form") &&
    !alvo.closest("[data-linha-rapida]");

  document.addEventListener("input", (evento) => {
    if (ehDoForm(evento.target)) agendar();
  });
  document.addEventListener("change", (evento) => {
    if (ehDoForm(evento.target)) void salvar();
  });

  // Enter em campo de uma linha só não envia o formulário: salva e pronto.
  form.addEventListener("submit", (evento) => {
    evento.preventDefault();
    void salvar();
  });

  // Ações de item já salvaram no servidor: só refletir o estado.
  document.addEventListener("orcamento:salvo", (evento) => {
    aplicarResposta(evento.detail || {});
    mostrar("Tudo salvo", "ok");
  });

  const navegar = async (botao, url) => {
    if (botao.disabled) return;
    clearTimeout(timer);
    if (salvando || ultimoEnviado !== assinatura(dadosDoForm())) await salvar();
    btnDesfazer.disabled = true;
    btnRefazer.disabled = true;
    mostrar(botao === btnDesfazer ? "Desfazendo…" : "Refazendo…", "salvando");
    const resposta = await fetch(url, {
      method: "POST",
      headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() },
      credentials: "same-origin",
    });
    const corpo = await resposta.json().catch(() => ({}));
    if (!resposta.ok) {
      mostrar(corpo.erro || "Não foi possível.", "erro");
      aplicarHistorico(corpo.historico);
      return;
    }
    try {
      sessionStorage.setItem(
        CHAVE_POSICAO,
        JSON.stringify({ y: window.scrollY, aviso: corpo.mensagem || "" })
      );
    } catch (error_) {
      // sem sessionStorage, só recarrega no topo
    }
    location.reload();
  };

  btnDesfazer.addEventListener("click", () => void navegar(btnDesfazer, barra.dataset.urlDesfazer));
  btnRefazer.addEventListener("click", () => void navegar(btnRefazer, barra.dataset.urlRefazer));

  document.addEventListener("keydown", (evento) => {
    if (!(evento.ctrlKey || evento.metaKey) || evento.altKey) return;
    // Dentro de um campo de texto, Ctrl+Z é o desfazer do próprio campo.
    if (evento.target.closest("input, textarea, select, [contenteditable='true']")) return;
    const tecla = evento.key.toLowerCase();
    if (tecla === "z" && !evento.shiftKey) {
      evento.preventDefault();
      void navegar(btnDesfazer, barra.dataset.urlDesfazer);
    } else if ((tecla === "z" && evento.shiftKey) || tecla === "y") {
      evento.preventDefault();
      void navegar(btnRefazer, barra.dataset.urlRefazer);
    }
  });

  window.addEventListener("beforeunload", (evento) => {
    if (salvando || timer !== null && statusEl.dataset.tipo === "pendente") evento.preventDefault();
  });

  // Depois de desfazer/refazer: volta para a mesma rolagem e mostra o que fez.
  try {
    const salvo = JSON.parse(sessionStorage.getItem(CHAVE_POSICAO) || "null");
    sessionStorage.removeItem(CHAVE_POSICAO);
    if (salvo) {
      window.scrollTo(0, salvo.y || 0);
      if (salvo.aviso) mostrar(salvo.aviso, "ok");
    }
  } catch (error_) {
    // ignora
  }

  ultimoEnviado = assinatura(dadosDoForm());
})();
