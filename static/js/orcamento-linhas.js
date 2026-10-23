/* Edição de quantidade e valor direto na linha do item (tela do orçamento).
 *
 * Enquanto o usuário digita, o subtotal da linha muda na hora (conta local,
 * a mesma do modelo). Ao parar de digitar, sair do campo ou apertar Enter, a
 * linha é salva e o servidor devolve os totais oficiais do orçamento, que
 * substituem o card de totais e a barra fixa. A conta local é só prévia: o
 * número que vale é sempre o do servidor.
 */
(() => {
  "use strict";

  const ESPERA_MS = 700;
  const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const decimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  // Mesma regra do parse_decimal_br do servidor: com vírgula e ponto, o ponto
  // é milhar; só vírgula, ela é a decimal; só ponto, ele é a decimal.
  const lerNumero = (texto) => {
    let s = String(texto || "").replace(/R\$|\s/g, "").trim();
    if (!s) return NaN;
    if (s.includes(",") && s.includes(".")) s = s.replace(/\./g, "").replace(",", ".");
    else if (s.includes(",")) s = s.replace(",", ".");
    return Number(s);
  };
  const arred = (v) => Math.round((v + Number.EPSILON) * 100) / 100;

  const csrf = () => {
    const campo = document.querySelector("input[name='csrfmiddlewaretoken']");
    return campo ? campo.value : "";
  };

  const estado = new WeakMap(); // linha -> { timer, salvando, pendente }
  const pegarEstado = (linha) => {
    if (!estado.has(linha)) estado.set(linha, { timer: null, salvando: false, pendente: false });
    return estado.get(linha);
  };
  let pendentes = 0;

  const status = (linha, texto, tipo) => {
    const alvo = linha.querySelector("[data-linha-status]");
    if (!alvo) return;
    alvo.textContent = texto;
    alvo.dataset.tipo = tipo || "";
  };

  const previaSubtotal = (linha) => {
    const qtd = lerNumero(linha.querySelector("[data-campo-rapido='quantidade']").value);
    const valor = lerNumero(linha.querySelector("[data-campo-rapido='valor_unitario']").value);
    const saida = linha.querySelector("[data-linha-subtotal]");
    if (!saida || !Number.isFinite(qtd) || !Number.isFinite(valor)) return;
    const base = qtd * valor;
    const n = (chave) => Number(linha.dataset[chave] || 0);
    let subtotal =
      base - n("descValor") - arred((base * n("descPct")) / 100) +
      n("acrValor") + arred((base * n("acrPct")) / 100);
    if (subtotal < 0) subtotal = 0;
    saida.textContent = moeda.format(arred(subtotal));
  };

  const aplicarTotais = (dados) => {
    const totais = document.getElementById("totais-card-region");
    if (totais && dados.totais_html !== undefined) totais.innerHTML = dados.totais_html;
    const barra = document.getElementById("ledger-bar");
    if (barra) {
      const total = barra.querySelector("[data-ledger-total]");
      const sub = barra.querySelector("[data-ledger-subtotal]");
      if (total) total.textContent = dados.total_final;
      if (sub) sub.textContent = dados.subtotal_itens;
    }
  };

  const salvar = async (linha) => {
    const est = pegarEstado(linha);
    clearTimeout(est.timer);
    if (est.salvando) {
      est.pendente = true; // salva de novo quando a requisição atual voltar
      return;
    }
    const qtd = linha.querySelector("[data-campo-rapido='quantidade']");
    const valor = linha.querySelector("[data-campo-rapido='valor_unitario']");
    if (qtd.dataset.salvo === qtd.value && valor.dataset.salvo === valor.value) return;

    est.salvando = true;
    pendentes += 1;
    status(linha, "Salvando…", "salvando");
    const enviado = { qtd: qtd.value, valor: valor.value };
    const corpo = new FormData();
    corpo.append("quantidade", enviado.qtd);
    corpo.append("valor_unitario", enviado.valor);
    try {
      const resposta = await fetch(linha.dataset.linhaRapida, {
        method: "POST",
        headers: { "X-Requested-With": "XMLHttpRequest", "X-CSRFToken": csrf() },
        body: corpo,
        credentials: "same-origin",
      });
      const dados = await resposta.json().catch(() => ({}));
      if (!resposta.ok) throw new Error(dados.erro || "Não foi possível salvar.");

      // Reformata só o campo que não mudou desde o envio e que não está em
      // foco. Se o usuário seguiu digitando, a referência fica no valor
      // ENVIADO, e a comparação no próximo salvar() percebe a diferença.
      const assentar = (campo, enviadoAgora, formatado) => {
        if (campo.value !== enviadoAgora) {
          campo.dataset.salvo = enviadoAgora;
          return;
        }
        if (document.activeElement !== campo) campo.value = formatado;
        campo.dataset.salvo = campo.value;
      };
      assentar(qtd, enviado.qtd, dados.quantidade);
      assentar(valor, enviado.valor, decimal.format(lerNumero(dados.valor_unitario)));
      qtd.removeAttribute("aria-invalid");
      valor.removeAttribute("aria-invalid");
      linha.querySelector("[data-linha-subtotal]").textContent = dados.subtotal;
      aplicarTotais(dados);
      status(linha, "Salvo", "ok");
      setTimeout(() => {
        const alvo = linha.querySelector("[data-linha-status]");
        if (alvo && alvo.dataset.tipo === "ok") status(linha, "", "");
      }, 1800);
    } catch (erro) {
      status(linha, erro.message, "erro");
      qtd.setAttribute("aria-invalid", "true");
      valor.setAttribute("aria-invalid", "true");
    } finally {
      est.salvando = false;
      pendentes -= 1;
      if (est.pendente) {
        est.pendente = false;
        salvar(linha);
      }
    }
  };

  const marcarSalvos = (escopo) => {
    escopo.querySelectorAll("[data-campo-rapido]").forEach((campo) => {
      if (campo.dataset.salvo === undefined) campo.dataset.salvo = campo.value;
    });
  };

  document.addEventListener("input", (evento) => {
    const campo = evento.target.closest("[data-campo-rapido]");
    if (!campo) return;
    const linha = campo.closest("[data-linha-rapida]");
    if (!linha) return;
    previaSubtotal(linha);
    status(linha, "", "");
    const est = pegarEstado(linha);
    clearTimeout(est.timer);
    est.timer = setTimeout(() => salvar(linha), ESPERA_MS);
  });

  document.addEventListener("change", (evento) => {
    const campo = evento.target.closest("[data-campo-rapido]");
    const linha = campo && campo.closest("[data-linha-rapida]");
    if (linha) salvar(linha);
  });

  document.addEventListener("keydown", (evento) => {
    const campo = evento.target.closest("[data-campo-rapido]");
    if (!campo || evento.key !== "Enter") return;
    evento.preventDefault();
    const linha = campo.closest("[data-linha-rapida]");
    salvar(linha);
    // Enter desce para o mesmo campo da linha de baixo, como numa planilha.
    const proxima = linha.nextElementSibling;
    const alvo = proxima && proxima.querySelector(`[data-campo-rapido='${campo.dataset.campoRapido}']`);
    if (alvo) {
      alvo.focus();
      alvo.select();
    }
  });

  document.addEventListener("focusin", (evento) => {
    const campo = evento.target.closest("[data-campo-rapido]");
    if (campo) campo.select();
  });

  window.addEventListener("beforeunload", (evento) => {
    if (pendentes > 0) {
      evento.preventDefault();
      evento.returnValue = "";
    }
  });

  // A tabela é trocada inteira por outras ações (adicionar, mover, duplicar):
  // os campos novos chegam sem o valor salvo de referência.
  const regiao = document.getElementById("itens-tabela-region");
  if (regiao) {
    marcarSalvos(regiao);
    new MutationObserver(() => marcarSalvos(regiao)).observe(regiao, { childList: true, subtree: true });
  }
})();
