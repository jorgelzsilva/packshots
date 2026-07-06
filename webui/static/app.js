/*
 * Packshots Web UI — upload, verificação, progresso (SSE) e downloads.
 */
(function () {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));

  // ---------- Estado ----------
  let mode = 'capa';
  let capaFiles = [];        // modo capa: lista de PDFs
  let capaEmptySlots = 1;    // slots vazios visíveis no modo capa
  let slotFiles = { miolo: null, capa: null, epub: null }; // modo packshots (slots)
  let batchFiles = [];       // modo packshots (lote via pasta)
  let jobId = null;
  let eventSource = null;

  const states = {
    setup: $('#state-setup'),
    warnings: $('#state-warnings'),
    processing: $('#state-processing'),
    results: $('#state-results'),
  };

  function mostrarEstado(nome) {
    Object.entries(states).forEach(([k, el]) => el.classList.toggle('hidden', k !== nome));
  }

  // ---------- Toggle de modo ----------
  $$('.mode-option').forEach((btn) => {
    btn.addEventListener('click', () => {
      mode = btn.dataset.mode;
      $$('.mode-option').forEach((b) => b.classList.toggle('active', b === btn));
      $('.mode-toggle').classList.toggle('packshots', mode === 'packshots');
      $('#panel-capa').classList.toggle('hidden', mode !== 'capa');
      $('#panel-packshots').classList.toggle('hidden', mode !== 'packshots');
      atualizarBotaoProcessar();
    });
  });

  // ---------- Entrada de arquivos (input oculto) ----------
  const fileInput = $('#file-input');
  let fileInputCallback = null;

  function abrirSeletor(accept, multiple, callback) {
    fileInput.accept = accept;
    fileInput.multiple = multiple;
    fileInputCallback = callback;
    fileInput.value = '';
    fileInput.click();
  }

  fileInput.addEventListener('change', () => {
    if (fileInputCallback && fileInput.files.length) {
      fileInputCallback(Array.from(fileInput.files));
    }
  });

  // ---------- Modo Capa: slots dinâmicos ----------
  const capaSlotsEl = $('#capa-slots');

  function renderCapaSlots() {
    capaSlotsEl.innerHTML = '';

    capaFiles.forEach((file, i) => {
      const slot = document.createElement('div');
      slot.className = 'slot filled';
      slot.innerHTML = `
        <span class="slot-label">Capa ${i + 1}</span>
        <span class="slot-file">${file.name}</span>
        <button class="slot-remove" title="Remover">✕</button>`;
      slot.querySelector('.slot-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        capaFiles.splice(i, 1);
        renderCapaSlots();
        atualizarBotaoProcessar();
      });
      capaSlotsEl.appendChild(slot);
    });

    for (let i = 0; i < capaEmptySlots; i++) {
      const slot = document.createElement('div');
      slot.className = 'slot';
      slot.innerHTML = `
        <span class="slot-label">Arraste um PDF de capa</span>
        <span class="slot-file">ou clique para escolher</span>`;
      slot.addEventListener('click', () =>
        abrirSeletor('.pdf', true, (files) => adicionarCapas(files)));
      registrarDrop(slot, (files) => adicionarCapas(files));
      capaSlotsEl.appendChild(slot);
    }
  }

  function adicionarCapas(files) {
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith('.pdf'));
    capaFiles.push(...pdfs);
    capaEmptySlots = Math.max(1, capaEmptySlots - pdfs.length);
    renderCapaSlots();
    atualizarBotaoProcessar();
  }

  $('#btn-add-slot').addEventListener('click', () => {
    capaEmptySlots++;
    renderCapaSlots();
  });

  // ---------- Modo Packshots: slots nomeados ----------
  $$('#panel-packshots .slot').forEach((slot) => {
    const nome = slot.dataset.slot;
    const accept = nome === 'epub' ? '.epub' : '.pdf';

    slot.addEventListener('click', () => {
      if (slotFiles[nome]) return;
      abrirSeletor(accept, false, (files) => atribuirSlot(nome, files[0]));
    });
    registrarDrop(slot, (files) => atribuirSlot(nome, files[0]));
  });

  function atribuirSlot(nome, file) {
    if (!file) return;
    const ext = nome === 'epub' ? '.epub' : '.pdf';
    if (!file.name.toLowerCase().endsWith(ext)) return;
    slotFiles[nome] = file;
    renderSlotPackshots(nome);
    atualizarBotaoProcessar();
  }

  function renderSlotPackshots(nome) {
    const slot = document.querySelector(`#panel-packshots .slot[data-slot="${nome}"]`);
    const fileEl = slot.querySelector('.slot-file');
    const file = slotFiles[nome];
    slot.classList.toggle('filled', !!file);
    slot.querySelector('.slot-remove')?.remove();

    if (file) {
      fileEl.textContent = file.name;
      const btn = document.createElement('button');
      btn.className = 'slot-remove';
      btn.title = 'Remover';
      btn.textContent = '✕';
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        slotFiles[nome] = null;
        renderSlotPackshots(nome);
        atualizarBotaoProcessar();
      });
      slot.appendChild(btn);
    } else {
      fileEl.textContent = '';
    }
  }

  // ---------- Modo Packshots: lote (pasta) ----------
  const batchZone = $('#batch-zone');

  registrarDrop(batchZone, null, async (dataTransfer) => {
    batchFiles = await coletarArquivos(dataTransfer);
    batchZone.classList.toggle('filled', batchFiles.length > 0);
    $('#batch-info').textContent = batchFiles.length
      ? `${batchFiles.length} arquivo(s) carregado(s)` : '';
    atualizarBotaoProcessar();
  });

  async function coletarArquivos(dataTransfer) {
    const arquivos = [];
    const entradas = [];

    for (const item of dataTransfer.items) {
      const entry = item.webkitGetAsEntry && item.webkitGetAsEntry();
      if (entry) entradas.push(entry);
    }

    async function percorrer(entry) {
      if (entry.isFile) {
        const file = await new Promise((res, rej) => entry.file(res, rej));
        const nome = file.name.toLowerCase();
        if (nome.endsWith('.pdf') || nome.endsWith('.epub')) arquivos.push(file);
      } else if (entry.isDirectory) {
        const reader = entry.createReader();
        let lote;
        do {
          lote = await new Promise((res, rej) => reader.readEntries(res, rej));
          for (const filho of lote) await percorrer(filho);
        } while (lote.length > 0);
      }
    }

    for (const entry of entradas) await percorrer(entry);

    // Fallback quando webkitGetAsEntry não está disponível
    if (!entradas.length) {
      for (const file of dataTransfer.files) {
        const nome = file.name.toLowerCase();
        if (nome.endsWith('.pdf') || nome.endsWith('.epub')) arquivos.push(file);
      }
    }
    return arquivos;
  }

  // ---------- Drag & drop genérico ----------
  function registrarDrop(el, onFiles, onDataTransfer) {
    el.addEventListener('dragover', (e) => {
      e.preventDefault();
      el.classList.add('dragover');
    });
    el.addEventListener('dragleave', () => el.classList.remove('dragover'));
    el.addEventListener('drop', (e) => {
      e.preventDefault();
      el.classList.remove('dragover');
      if (onDataTransfer) onDataTransfer(e.dataTransfer);
      else if (onFiles) onFiles(Array.from(e.dataTransfer.files));
    });
  }

  // Evita que soltar fora dos alvos navegue para o arquivo
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  // ---------- Botão Processar ----------
  const btnProcess = $('#btn-process');

  function atualizarBotaoProcessar() {
    const pronto = mode === 'capa'
      ? capaFiles.length > 0
      : (batchFiles.length > 0 || !!slotFiles.miolo);
    btnProcess.disabled = !pronto;
  }

  $$('.chip input').forEach((chk) => chk.addEventListener('change', atualizarBotaoProcessar));

  btnProcess.addEventListener('click', enviarJob);

  async function enviarJob() {
    btnProcess.disabled = true;
    $('#setup-error').textContent = '';

    const form = new FormData();
    form.append('mode', mode);

    if (mode === 'capa') {
      const opts = {};
      $$('#panel-capa .chip input').forEach((chk) => {
        if (chk.dataset.opt === 'orelhas') {
          opts.orelha_esq = chk.checked;
          opts.orelha_dir = chk.checked;
        } else {
          opts[chk.dataset.opt] = chk.checked;
        }
      });
      form.append('options', JSON.stringify(opts));
      capaFiles.forEach((f) => form.append('files', f));
    } else if (batchFiles.length) {
      batchFiles.forEach((f) => form.append('files', f));
    } else {
      const mapa = {};
      for (const [slot, file] of Object.entries(slotFiles)) {
        if (file) {
          mapa[file.name] = slot;
          form.append('files', file);
        }
      }
      form.append('slots', JSON.stringify(mapa));
    }

    let resposta;
    try {
      const res = await fetch('/api/jobs', { method: 'POST', body: form });
      resposta = await res.json();
      if (!res.ok) throw new Error(resposta.detail || 'Falha no envio.');
    } catch (err) {
      $('#setup-error').textContent = err.message;
      atualizarBotaoProcessar();
      return;
    }

    jobId = resposta.job_id;

    if (resposta.warnings && resposta.warnings.length) {
      renderAvisos(resposta.warnings);
      mostrarEstado('warnings');
    } else {
      iniciarProcessamento(resposta.packs);
    }
  }

  // ---------- Avisos de anotações ----------
  function renderAvisos(avisos) {
    const lista = $('#warnings-list');
    lista.innerHTML = '';
    for (const pack of avisos) {
      const div = document.createElement('div');
      div.className = 'warn-pack';
      const itens = pack.warnings.flatMap((w) =>
        w.anotacoes.map((a) => `
          <div class="warn-item">
            <b>${w.arquivo}</b> — pág. ${a.pagina} · ${a.tipo}
            ${a.autor ? ` · ${a.autor}` : ''}
            ${a.texto ? `<br>“${a.texto}”` : ''}
          </div>`)
      ).join('');
      div.innerHTML = `<h3>${pack.ident}</h3>${itens}`;
      lista.appendChild(div);
    }
  }

  async function decidir(action) {
    const res = await fetch(`/api/jobs/${jobId}/decision`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action }),
    });
    const job = await res.json();

    if (action === 'stop') {
      resetar();
      return;
    }
    iniciarProcessamento(job.packs);
  }

  $('#btn-continue').addEventListener('click', () => decidir('continue_all'));
  $('#btn-skip').addEventListener('click', () => decidir('skip_flagged'));
  $('#btn-stop').addEventListener('click', () => decidir('stop'));

  // ---------- Processamento (SSE) ----------
  const packRows = {};

  function iniciarProcessamento(packs) {
    mostrarEstado('processing');
    $('#progress-pct').innerHTML = '0<small>%</small>';
    $('#progress-fill').style.width = '0%';
    $('#progress-msg').textContent = 'Iniciando…';

    const container = $('#packs-progress');
    container.innerHTML = '';
    Object.keys(packRows).forEach((k) => delete packRows[k]);

    for (const pack of packs || []) {
      const row = document.createElement('div');
      row.className = 'pack-row' + (pack.skipped ? ' pulado' : '');
      row.innerHTML = `
        <span class="pack-name">${pack.ident}</span>
        <span class="pack-status">${pack.skipped ? 'pulado' : 'aguardando'}</span>
        <div class="pack-bar"><div class="pack-bar-fill"></div></div>`;
      container.appendChild(row);
      packRows[pack.ident] = row;
    }

    eventSource = new EventSource(`/api/jobs/${jobId}/events`);
    eventSource.onmessage = (e) => tratarEvento(JSON.parse(e.data));
    eventSource.addEventListener('close', () => {
      eventSource.close();
      eventSource = null;
    });
  }

  function atualizarOverall(pct) {
    $('#progress-pct').innerHTML = `${Math.round(pct)}<small>%</small>`;
    $('#progress-fill').style.width = `${pct}%`;
  }

  function tratarEvento(ev) {
    const row = ev.ident ? packRows[ev.ident] : null;

    switch (ev.type) {
      case 'pack_start':
        if (row) row.querySelector('.pack-status').textContent = 'processando…';
        break;

      case 'pack_progress':
        if (row) {
          row.querySelector('.pack-bar-fill').style.width = `${ev.pct}%`;
          row.querySelector('.pack-status').textContent = `${Math.round(ev.pct)}%`;
        }
        atualizarOverall(ev.overall_pct);
        $('#progress-msg').textContent = `${ev.ident}: ${ev.message}`;
        break;

      case 'pack_done':
        if (row) {
          row.querySelector('.pack-bar-fill').style.width = '100%';
          row.querySelector('.pack-status').textContent = 'concluído ✓';
        }
        atualizarOverall(ev.overall_pct);
        break;

      case 'pack_error':
        if (row) {
          row.classList.add('erro');
          row.querySelector('.pack-status').textContent = `erro: ${ev.message}`;
        }
        break;

      case 'warning':
        $('#progress-msg').textContent = ev.message;
        break;

      case 'job_done':
        atualizarOverall(100);
        mostrarResultados();
        break;
    }
  }

  // ---------- Resultados ----------
  async function mostrarResultados() {
    const res = await fetch(`/api/jobs/${jobId}/results`);
    const dados = await res.json();

    const lista = $('#results-list');
    lista.innerHTML = '';

    for (const pack of dados.packs) {
      const div = document.createElement('div');
      div.className = 'result-pack' + (pack.status === 'erro' ? ' erro' : '');

      let corpo = '';
      if (pack.status === 'erro') {
        corpo = `<p class="pack-note">Erro: ${pack.error}</p>`;
      } else if (pack.skipped) {
        corpo = '<p class="pack-note">Pulado (continha comentários).</p>';
      } else if (!pack.outputs.length) {
        corpo = '<p class="pack-note">Nenhum arquivo gerado.</p>';
      } else {
        corpo = pack.outputs.map((o) => `
          <div class="result-file">
            <span>${o.name}</span>
            <span class="file-size">${formatarTamanho(o.size)}</span>
            <a href="${o.url}" download>Baixar ↓</a>
          </div>`).join('');
      }

      div.innerHTML = `<h3>${pack.ident}</h3>${corpo}`;
      lista.appendChild(div);
    }

    $('#btn-download-all').href = dados.zip_url;
    mostrarEstado('results');
  }

  function formatarTamanho(bytes) {
    if (bytes > 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes > 1024) return Math.round(bytes / 1024) + ' KB';
    return bytes + ' B';
  }

  // ---------- Reiniciar ----------
  $('#btn-restart').addEventListener('click', resetar);

  function resetar() {
    if (eventSource) { eventSource.close(); eventSource = null; }
    jobId = null;
    capaFiles = [];
    capaEmptySlots = 1;
    slotFiles = { miolo: null, capa: null, epub: null };
    batchFiles = [];
    batchZone.classList.remove('filled');
    $('#batch-info').textContent = '';
    ['miolo', 'capa', 'epub'].forEach(renderSlotPackshots);
    renderCapaSlots();
    atualizarBotaoProcessar();
    $('#setup-error').textContent = '';
    mostrarEstado('setup');
  }

  // ---------- Inicialização ----------
  renderCapaSlots();
  atualizarBotaoProcessar();
})();
