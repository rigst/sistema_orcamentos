/*
 * Abas da tela do orçamento (Itens, Evento, Comercial, Contrato).
 *
 * Todos os campos continuam num formulário só, então trocar de aba não perde
 * nada. A aba aberta fica no hash da URL (#evento, #contrato...) para o
 * "voltar" e o redirect do servidor caírem no lugar certo. Se o servidor
 * devolver o formulário com erro, abre a primeira aba que tem erro.
 */
(() => {
  "use strict";

  const lista = document.querySelector("[data-orc-abas]");
  if (!lista) return;

  const abas = Array.from(lista.querySelectorAll("[role='tab']"));
  const painel = (nome) => document.querySelector(`[data-painel='${nome}']`);
  const nomes = abas.map((aba) => aba.dataset.aba);

  const ativar = (nome, { foco = false, historico = true } = {}) => {
    if (!nomes.includes(nome)) nome = "itens";
    abas.forEach((aba) => {
      const ativa = aba.dataset.aba === nome;
      aba.setAttribute("aria-selected", ativa ? "true" : "false");
      aba.tabIndex = ativa ? 0 : -1;
      const alvo = painel(aba.dataset.aba);
      if (alvo) alvo.hidden = !ativa;
      if (ativa && foco) aba.focus();
    });
    if (historico) {
      const hash = nome === "itens" ? "" : `#${nome}`;
      history.replaceState(null, "", `${location.pathname}${location.search}${hash}`);
    }
  };

  lista.addEventListener("click", (event) => {
    const aba = event.target.closest("[role='tab']");
    if (aba) ativar(aba.dataset.aba);
  });

  // Setas e Home/End, como o padrão de abas da WAI-ARIA.
  lista.addEventListener("keydown", (event) => {
    const atual = abas.findIndex((aba) => aba.getAttribute("aria-selected") === "true");
    const destinos = {
      ArrowRight: (atual + 1) % abas.length,
      ArrowLeft: (atual - 1 + abas.length) % abas.length,
      Home: 0,
      End: abas.length - 1,
    };
    if (!(event.key in destinos)) return;
    event.preventDefault();
    ativar(abas[destinos[event.key]].dataset.aba, { foco: true });
  });

  const comErro = nomes.find((nome) => {
    const alvo = painel(nome);
    return alvo?.querySelector(".errorlist, .ds-help--error, [aria-invalid='true']");
  });
  ativar(comErro || location.hash.slice(1) || "itens", { historico: Boolean(comErro) });
})();
