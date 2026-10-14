/* NoteLab — interações e efeitos */
(function () {
    'use strict';

    const reduzirMovimento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const $ = (sel, el = document) => el.querySelector(sel);
    const $$ = (sel, el = document) => Array.from(el.querySelectorAll(sel));

    function guardar(chave, valor) { try { localStorage.setItem(chave, valor); } catch (e) { /* sem storage */ } }
    function ler(chave) { try { return localStorage.getItem(chave); } catch (e) { return null; } }

    /* ------------------------------------------------ fundo: rede de partículas */
    function iniciarFundo() {
        const canvas = $('#fx-bg');
        if (!canvas || reduzirMovimento) return;
        const ctx = canvas.getContext('2d');
        let w, h, pontos = [], dpr = Math.min(window.devicePixelRatio || 1, 2);
        const mouse = { x: -9999, y: -9999 };

        function redimensionar() {
            w = canvas.clientWidth; h = canvas.clientHeight;
            canvas.width = w * dpr; canvas.height = h * dpr;
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            const qtd = Math.min(Math.floor((w * h) / 22000), 90);
            pontos = Array.from({ length: qtd }, () => ({
                x: Math.random() * w, y: Math.random() * h,
                vx: (Math.random() - .5) * .25, vy: (Math.random() - .5) * .25,
                r: Math.random() * 1.4 + .4,
                hue: Math.random() < .7 ? '34,227,255' : '155,123,255',
            }));
        }

        function quadro() {
            ctx.clearRect(0, 0, w, h);
            for (const p of pontos) {
                p.x += p.vx; p.y += p.vy;
                if (p.x < 0 || p.x > w) p.vx *= -1;
                if (p.y < 0 || p.y > h) p.vy *= -1;
            }
            for (let i = 0; i < pontos.length; i++) {
                const a = pontos[i];
                for (let j = i + 1; j < pontos.length; j++) {
                    const b = pontos[j];
                    const dx = a.x - b.x, dy = a.y - b.y, d2 = dx * dx + dy * dy;
                    if (d2 < 15000) {
                        ctx.strokeStyle = `rgba(${a.hue},${(1 - d2 / 15000) * .18})`;
                        ctx.lineWidth = .6;
                        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
                    }
                }
                const mx = a.x - mouse.x, my = a.y - mouse.y, md = mx * mx + my * my;
                if (md < 30000) {
                    ctx.strokeStyle = `rgba(34,227,255,${(1 - md / 30000) * .35})`;
                    ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(mouse.x, mouse.y); ctx.stroke();
                }
                ctx.fillStyle = `rgba(${a.hue},.8)`;
                ctx.beginPath(); ctx.arc(a.x, a.y, a.r, 0, Math.PI * 2); ctx.fill();
            }
            requestAnimationFrame(quadro);
        }

        window.addEventListener('resize', redimensionar);
        window.addEventListener('mousemove', (e) => { mouse.x = e.clientX; mouse.y = e.clientY; });
        window.addEventListener('mouseleave', () => { mouse.x = mouse.y = -9999; });
        redimensionar();
        requestAnimationFrame(quadro);
    }

    /* ------------------------------------------------ relógio */
    function iniciarRelogio() {
        const el = $('.relogio');
        if (!el) return;
        const hora = $('.hora', el), data = $('.data', el);
        const fmtData = new Intl.DateTimeFormat('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' });
        function tick() {
            const agora = new Date();
            hora.textContent = agora.toLocaleTimeString('pt-BR');
            data.textContent = fmtData.format(agora).replace(/\./g, '');
        }
        tick();
        setInterval(tick, 1000);
    }

    /* ------------------------------------------------ números animados */
    function animarNumeros() {
        $$('[data-count]').forEach((el) => {
            const alvo = parseInt(el.dataset.count, 10) || 0;
            if (reduzirMovimento || alvo === 0) { el.textContent = alvo; return; }
            const dur = 1100, t0 = performance.now();
            function passo(t) {
                const k = Math.min((t - t0) / dur, 1);
                const ease = 1 - Math.pow(1 - k, 3);
                el.textContent = Math.round(alvo * ease);
                if (k < 1) requestAnimationFrame(passo);
            }
            requestAnimationFrame(passo);
        });
        $$('.ring[data-pct]').forEach((el) => {
            const barra = $('.barra', el);
            const pct = Math.max(0, Math.min(100, parseInt(el.dataset.pct, 10) || 0));
            requestAnimationFrame(() => { barra.style.strokeDashoffset = 226 - (226 * pct) / 100; });
        });
    }

    /* ------------------------------------------------ toasts */
    function iniciarToasts() {
        $$('.toast').forEach((t, i) => {
            t.style.animationDelay = `${i * 120}ms`;
            const fechar = () => { t.classList.add('saindo'); setTimeout(() => t.remove(), 400); };
            $('button', t)?.addEventListener('click', fechar);
            setTimeout(fechar, 6000 + i * 120);
        });
    }

    /* ------------------------------------------------ menu mobile */
    function iniciarMenu() {
        $('.menu-toggle')?.addEventListener('click', () => document.body.classList.toggle('menu-aberto'));
        document.addEventListener('click', (e) => {
            if (document.body.classList.contains('menu-aberto') && !e.target.closest('.sidebar, .menu-toggle')) {
                document.body.classList.remove('menu-aberto');
            }
        });
    }

    /* ------------------------------------------------ modais
       Botões com data-modal="#id" abrem o <dialog>. Atributos data-action e
       data-* extras preenchem o form e os elementos [data-fill="nome"]. */
    function iniciarModais() {
        $$('[data-modal]').forEach((btn) => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const dlg = $(btn.dataset.modal);
                if (!dlg) return;
                const form = $('form', dlg);
                if (form && btn.dataset.action) form.action = btn.dataset.action;
                $$('[data-fill]', dlg).forEach((alvo) => {
                    const v = btn.dataset[alvo.dataset.fill];
                    if (v !== undefined) alvo.textContent = v;
                });
                form?.reset();
                dlg.showModal();
                $('textarea, input:not([type=hidden])', dlg)?.focus();
            });
        });
        $$('dialog.modal').forEach((dlg) => {
            dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.close(); });
            $$('[data-fechar]', dlg).forEach((b) => b.addEventListener('click', () => dlg.close()));
        });
    }

    /* Formulários com data-confirmar pedem confirmação no modal genérico */
    function iniciarConfirmacoes() {
        const dlg = $('#modal-confirmar');
        if (!dlg) return;
        let pendente = null;
        $$('form[data-confirmar]').forEach((form) => {
            form.addEventListener('submit', (e) => {
                if (form.dataset.confirmado) return;
                e.preventDefault();
                pendente = form;
                $('[data-fill="texto"]', dlg).textContent = form.dataset.confirmar;
                dlg.showModal();
            });
        });
        $('[data-ok]', dlg).addEventListener('click', () => {
            if (!pendente) return;
            pendente.dataset.confirmado = '1';
            dlg.close();
            pendente.requestSubmit ? pendente.requestSubmit() : pendente.submit();
        });
    }

    /* ------------------------------------------------ lista de notebooks */
    function iniciarListaNotebooks() {
        const grade = $('.nb-grid');
        if (!grade) return;

        // grade x lista (lembrado por navegador)
        const botoes = $$('.view-toggle button');
        function aplicar(modo) {
            grade.classList.toggle('lista', modo === 'lista');
            botoes.forEach((b) => b.classList.toggle('ativo', b.dataset.view === modo));
        }
        aplicar(ler('nb-view') || 'grade');
        botoes.forEach((b) => b.addEventListener('click', () => { aplicar(b.dataset.view); guardar('nb-view', b.dataset.view); }));

        // filtro instantâneo enquanto digita (o Enter ainda faz a busca no servidor)
        const busca = $('.busca input');
        const cards = $$('.nb', grade);
        const vazio = $('#filtro-vazio');
        busca?.addEventListener('input', () => {
            const termo = busca.value.trim().toLowerCase();
            let visiveis = 0;
            cards.forEach((c) => {
                const ok = !termo || c.dataset.busca.includes(termo);
                c.classList.toggle('hide', !ok);
                if (ok) visiveis++;
            });
            vazio?.classList.toggle('hide', visiveis > 0);
        });
    }

    /* ------------------------------------------------ seletor de notebooks */
    function iniciarPicker() {
        const picker = $('.picker');
        if (!picker) return;
        const caixas = $$('input[type=checkbox]', picker);
        const contador = $('.picker-contador');
        const atualizar = () => {
            const n = caixas.filter((c) => c.checked).length;
            contador.textContent = `${n} selecionado${n === 1 ? '' : 's'}`;
        };
        caixas.forEach((c) => c.addEventListener('change', atualizar));
        $$('[data-selecionar]').forEach((btn) => btn.addEventListener('click', () => {
            const qtd = btn.dataset.selecionar === 'todos' ? caixas.length : parseInt(btn.dataset.selecionar, 10);
            caixas.forEach((c, i) => { c.checked = i < qtd; });
            atualizar();
        }));
        const filtro = $('#picker-filtro');
        filtro?.addEventListener('input', () => {
            const t = filtro.value.trim().toLowerCase();
            $$('.chip-nb', picker).forEach((ch) => ch.classList.toggle('hide', t && !ch.textContent.toLowerCase().includes(t)));
        });
        atualizar();
    }

    /* ------------------------------------------------ disponibilidade (agenda) */
    function iniciarDisponibilidade() {
        const box = $('#disp-box');
        if (!box) return;
        const form = box.closest('form');
        const campo = (n) => $(`[name=${n}]`, form);
        const grande = $('.grande', box), texto = $('.texto', box), conflitos = $('.conflitos', box);
        let timer;

        async function consultar() {
            const params = new URLSearchParams({
                data: campo('data').value, inicio: campo('hora_inicio').value, fim: campo('hora_fim').value,
                excluir: box.dataset.excluir || '',
            });
            if (!params.get('data') || !params.get('inicio') || !params.get('fim')) return;
            try {
                const r = await fetch(`${box.dataset.url}?${params}`, { headers: { 'X-Requested-With': 'fetch' } });
                if (!r.ok) {
                    box.className = 'disp-box'; grande.textContent = '—';
                    texto.textContent = 'Confira o horário (o fim precisa ser depois do início).';
                    conflitos.textContent = '';
                    return;
                }
                const d = await r.json();
                const qtd = parseInt(campo('quantidade').value, 10) || 0;
                grande.textContent = d.livres;
                box.className = 'disp-box ' + (qtd > d.livres ? 'ruim' : 'ok');
                texto.textContent = qtd > d.livres
                    ? `Faltam ${qtd - d.livres} notebook(s) para esse horário.`
                    : `livre(s) de ${d.frota} em funcionamento nesse horário.`;
                conflitos.textContent = d.conflitos.length
                    ? 'Já reservado: ' + d.conflitos.map((c) => `${c.titulo} (${c.inicio}–${c.fim}, ${c.quantidade} un.)`).join(' · ')
                    : 'Nenhuma outra reserva nesse horário.';
            } catch (e) { /* offline: ignora */ }
        }
        ['data', 'hora_inicio', 'hora_fim', 'quantidade'].forEach((n) => {
            campo(n)?.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(consultar, 250); });
        });
        consultar();
    }

    /* ------------------------------------------------ efeito de digitação */
    function iniciarDigitacao() {
        $$('[data-typing]').forEach((el) => {
            const texto = el.dataset.typing;
            if (reduzirMovimento) { el.textContent = texto; return; }
            el.classList.add('typing');
            let i = 0;
            const t = setInterval(() => {
                el.textContent = texto.slice(0, ++i);
                if (i >= texto.length) clearInterval(t);
            }, 45);
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        iniciarFundo();
        iniciarRelogio();
        animarNumeros();
        iniciarToasts();
        iniciarMenu();
        iniciarModais();
        iniciarConfirmacoes();
        iniciarListaNotebooks();
        iniciarPicker();
        iniciarDisponibilidade();
        iniciarDigitacao();
    });
})();
