"""
Adaptadores de Pipeline para a Web UI
-------------------------------------
Cada saída (capa, contracapa, ensaio, vitrines, sumário...) é tratada como um
"artefato" independente, que pode ser gerado no fluxo normal e reprocessado
individualmente (botão "Tentar de novo") caso falhe.
"""
import os

from modules.utils import garantir_pasta
from modules.detector import processar_capa
from modules.miolo import gerar_ensaio, gerar_vitrines, gerar_sumario

# Rótulos em pt-BR para a UI
ROTULOS = {
    'capa': 'Capa',
    'quarta_capa': 'Contracapa',
    'lombada': 'Lombada',
    'orelha_esq': 'Orelha esquerda',
    'orelha_dir': 'Orelha direita',
    'ensaio': 'Ensaio de leitura',
    'vitrines': 'Imagens de vitrine',
    'sumario': 'Sumário (IA)',
}

PARTES_CAPA = ('capa', 'quarta_capa', 'lombada', 'orelha_esq', 'orelha_dir')


def artefatos_esperados(job, pack):
    """Lista de chaves de artefato que este pack deve gerar, na ordem de exibição."""
    if job.mode == 'capa':
        return [k for k in PARTES_CAPA if job.options.get(k)]

    keys = ['ensaio', 'vitrines', 'sumario']
    if pack.files.get('capa'):
        keys += ['capa', 'quarta_capa']
    return keys


def _info_arquivo(job, ident, caminho):
    return {
        'name': os.path.basename(caminho),
        'url': f'/api/jobs/{job.id}/files/{ident}/{os.path.basename(caminho)}',
        'size': os.path.getsize(caminho) if os.path.exists(caminho) else 0,
    }


def _gerar_parte_capa(pack, pasta, key):
    """Gera uma única parte da capa (capa, contracapa, lombada, orelha...)."""
    path_capa = pack.files.get('capa')
    if not path_capa:
        raise ValueError("Nenhum PDF de capa neste pacote.")
    cfg = {p: (p == key) for p in PARTES_CAPA}
    resultado = processar_capa(path_capa, pasta, pack.ident, config_exportar=cfg)
    if not resultado.get('estrutura'):
        raise ValueError("Marcas de corte não detectadas no PDF de capa.")
    if not resultado.get(key):
        raise ValueError(f"'{ROTULOS[key]}' não encontrada na estrutura da capa.")
    return [resultado[key]]


def _gerar_vitrines(pack, pasta):
    """Gera as vitrines; recria o ensaio antes se necessário."""
    ensaio = os.path.join(pasta, f"{pack.ident}_ensaiodeleitura.pdf")
    if not os.path.exists(ensaio):
        ensaio = gerar_ensaio(pack.files['miolo'], pack.ident, pasta)
    return gerar_vitrines(ensaio, pack.ident, pasta)


def gerar_artefato(job, pack, key, model=None):
    """
    Gera (ou regenera) um único artefato.

    Args:
        model: modelo de IA preferido para o sumário (opcional). Se não for
               informado, usa o definido no job (job.ai_model) ou o padrão.

    Returns:
        dict: {'key', 'label', 'status': 'ok'|'erro', 'error', 'files': [...]}
    """
    pasta = os.path.join(job.output_dir, pack.ident)
    garantir_pasta(pasta)

    artefato = {'key': key, 'label': ROTULOS.get(key, key), 'status': 'ok', 'error': '', 'files': []}
    try:
        if key in PARTES_CAPA:
            caminhos = _gerar_parte_capa(pack, pasta, key)
        elif key == 'ensaio':
            caminhos = [gerar_ensaio(pack.files['miolo'], pack.ident, pasta)]
        elif key == 'vitrines':
            caminhos = _gerar_vitrines(pack, pasta)
        elif key == 'sumario':
            modelo = model or getattr(job, 'ai_model', None)
            res = gerar_sumario(pack.files['miolo'], pack.files.get('epub'), pack.ident, pasta, model=modelo)
            if res['status'] != 'ok':
                raise ValueError(res['error'])
            caminhos = [res['sumario']]
        else:
            raise ValueError(f"Artefato desconhecido: {key}")

        artefato['files'] = [_info_arquivo(job, pack.ident, c) for c in caminhos if c]
        if not artefato['files']:
            raise ValueError("Nenhum arquivo gerado.")
    except Exception as e:
        artefato['status'] = 'erro'
        artefato['error'] = str(e)
    return artefato


def run_pack(job, pack, on_progress):
    """Gera todos os artefatos esperados do pack, um a um, reportando progresso."""
    esperados = artefatos_esperados(job, pack)
    if not esperados:
        raise ValueError("Nada a gerar para este pacote.")

    pack.artifacts = []
    total = len(esperados)
    for i, key in enumerate(esperados):
        on_progress(f"Gerando: {ROTULOS.get(key, key)}", i / total)
        artefato = gerar_artefato(job, pack, key)
        pack.artifacts.append(artefato)
        on_progress(f"{ROTULOS.get(key, key)}: {'ok' if artefato['status'] == 'ok' else 'falhou'}", (i + 1) / total)
