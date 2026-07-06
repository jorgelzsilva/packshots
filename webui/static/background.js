/*
 * Fundo animado: linhas verticais neon dançando como fogo em capim gelado.
 * Duas passadas de composição (desfocada + nítida) com blend aditivo.
 */
(function () {
  const canvas = document.getElementById('bg');
  const ctx = canvas.getContext('2d');

  const reduzirMovimento = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let largura, altura, linhas = [];
  const off = document.createElement('canvas');
  const offCtx = off.getContext('2d');

  function redimensionar() {
    largura = canvas.width = off.width = window.innerWidth;
    altura = canvas.height = off.height = window.innerHeight;
    criarLinhas();
  }

  function criarLinhas() {
    const qtd = Math.max(18, Math.min(40, Math.floor(largura / 42)));
    linhas = [];
    for (let i = 0; i < qtd; i++) {
      linhas.push({
        baseX: (i + 0.5) * (largura / qtd) + (Math.random() - 0.5) * 30,
        comprimento: altura * (0.35 + Math.random() * 0.55),
        yBase: altura * (0.75 + Math.random() * 0.3),
        amp1: 6 + Math.random() * 18,
        amp2: 2 + Math.random() * 8,
        freq1: 0.3 + Math.random() * 0.5,
        freq2: 0.9 + Math.random() * 1.4,
        fase: Math.random() * Math.PI * 2,
        alfaBase: 0.25 + Math.random() * 0.45,
        flickerVel: 1.5 + Math.random() * 3,
        espessura: 1 + Math.random() * 1.6,
      });
    }
  }

  function desenharLinhas(t) {
    offCtx.clearRect(0, 0, largura, altura);

    for (const l of linhas) {
      const flicker = 0.7 + 0.3 * Math.sin(t * l.flickerVel + l.fase * 3);
      const alfa = l.alfaBase * flicker;

      const yTopo = l.yBase - l.comprimento;
      const grad = offCtx.createLinearGradient(0, l.yBase, 0, yTopo);
      grad.addColorStop(0, 'rgba(60, 200, 255, 0)');
      grad.addColorStop(0.35, `rgba(60, 200, 255, ${alfa * 0.8})`);
      grad.addColorStop(0.75, `rgba(140, 230, 255, ${alfa})`);
      grad.addColorStop(1, 'rgba(200, 250, 255, 0)');

      offCtx.strokeStyle = grad;
      offCtx.lineWidth = l.espessura;
      offCtx.lineCap = 'round';
      offCtx.beginPath();

      // A ponta balança mais que a raiz — como capim ao vento
      const passos = 14;
      for (let s = 0; s <= passos; s++) {
        const p = s / passos;
        const y = l.yBase - p * l.comprimento;
        const forca = p * p; // raiz presa, ponta livre
        const x = l.baseX
          + forca * l.amp1 * Math.sin(t * l.freq1 + l.fase)
          + forca * l.amp2 * Math.sin(t * l.freq2 + l.fase * 2 + p * 3);
        if (s === 0) offCtx.moveTo(x, y);
        else offCtx.lineTo(x, y);
      }
      offCtx.stroke();
    }
  }

  function compor() {
    ctx.clearRect(0, 0, largura, altura);
    ctx.globalCompositeOperation = 'lighter';

    // Passada 1: brilho desfocado
    ctx.filter = 'blur(12px)';
    ctx.globalAlpha = 0.9;
    ctx.drawImage(off, 0, 0);

    // Passada 2: núcleo nítido
    ctx.filter = 'blur(1px)';
    ctx.globalAlpha = 0.8;
    ctx.drawImage(off, 0, 0);

    ctx.filter = 'none';
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
  }

  let ultimoFrame = 0;
  let pausado = false;
  const INTERVALO = 1000 / 30; // ~30fps

  function animar(agora) {
    if (!pausado) {
      if (agora - ultimoFrame >= INTERVALO) {
        ultimoFrame = agora;
        desenharLinhas(agora / 1000);
        compor();
      }
      requestAnimationFrame(animar);
    }
  }

  function frameEstatico() {
    desenharLinhas(1.7);
    compor();
  }

  window.addEventListener('resize', () => {
    redimensionar();
    if (reduzirMovimento) frameEstatico();
  });

  document.addEventListener('visibilitychange', () => {
    if (reduzirMovimento) return;
    if (document.hidden) {
      pausado = true;
    } else if (pausado) {
      pausado = false;
      requestAnimationFrame(animar);
    }
  });

  redimensionar();
  if (reduzirMovimento) {
    frameEstatico();
  } else {
    requestAnimationFrame(animar);
  }
})();
