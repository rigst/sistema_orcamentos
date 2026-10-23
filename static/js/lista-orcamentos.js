/*
 * Lista de orçamentos: a linha inteira abre o orçamento.
 *
 * O link de verdade fica no número (teclado e leitor de tela usam ele). O
 * clique no resto da linha segue o mesmo endereço, sem atrapalhar os
 * controles da própria linha (menu de status, ações, seleção de texto).
 * Ctrl/Cmd/botão do meio abrem em nova aba, como num link.
 */
(() => {
  "use strict";

  const INTERATIVOS = "a, button, input, select, textarea, summary, details, form, label";

  document.addEventListener("click", (evento) => {
    const linha = evento.target.closest("tr[data-href]");
    if (!linha || evento.target.closest(INTERATIVOS)) return;
    if (window.getSelection()?.toString()) return; // estava selecionando texto
    if (evento.ctrlKey || evento.metaKey || evento.shiftKey) {
      window.open(linha.dataset.href, "_blank", "noopener");
      return;
    }
    window.location.href = linha.dataset.href;
  });

  document.addEventListener("auxclick", (evento) => {
    const linha = evento.target.closest("tr[data-href]");
    if (!linha || evento.button !== 1 || evento.target.closest(INTERATIVOS)) return;
    window.open(linha.dataset.href, "_blank", "noopener");
  });
})();
