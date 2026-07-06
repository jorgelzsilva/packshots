"""
Adaptadores de Pipeline para a Web UI
-------------------------------------
Conectam os módulos existentes (detector/miolo) ao modelo de Job,
compondo o progresso por pack.
"""
import os

from modules.utils import garantir_pasta
from modules.detector import processar_capa
from modules.miolo import processar_miolo

# Pesos de progresso no fluxo completo (packshots)
PESO_MIOLO = 0.7
PESO_CAPA = 0.3


def run_pack_capa(job, pack, on_progress):
    """Modo 'Apenas Capa': processa o PDF de capa com as opções escolhidas na UI."""
    path_capa = pack.files.get('capa')
    assert path_capa, f"Pack '{pack.ident}' sem arquivo de capa."

    pasta_saida = os.path.join(job.output_dir, pack.ident)
    garantir_pasta(pasta_saida)

    resultado = processar_capa(
        path_capa, pasta_saida, pack.ident,
        config_exportar=job.options,
        on_progress=on_progress,
    )

    if not resultado['estrutura']:
        raise ValueError("Marcas de corte não detectadas no PDF de capa.")

    exportadas = [k for k, v in resultado.items() if v and k != 'estrutura']
    if not exportadas:
        raise ValueError("Nenhuma parte exportada — verifique as opções selecionadas.")

    return resultado


def run_pack_completo(job, pack, on_progress):
    """Modo 'Packshots': miolo (70%) + capa (30%)."""
    path_miolo = pack.files.get('miolo')
    path_capa = pack.files.get('capa')
    path_epub = pack.files.get('epub')
    assert path_miolo, f"Pack '{pack.ident}' sem arquivo de miolo."

    pasta_saida = os.path.join(job.output_dir, pack.ident)
    garantir_pasta(pasta_saida)

    processar_miolo(
        path_miolo, path_epub, pack.ident, pasta_saida,
        on_progress=lambda msg, frac: on_progress(msg, frac * PESO_MIOLO),
    )

    if path_capa:
        resultado = processar_capa(
            path_capa, pasta_saida, pack.ident,
            config_exportar={'capa': True, 'quarta_capa': True, 'lombada': False,
                             'orelha_esq': False, 'orelha_dir': False, 'debug': False},
            on_progress=lambda msg, frac: on_progress(msg, PESO_MIOLO + frac * PESO_CAPA),
        )
        if not resultado['estrutura']:
            on_progress("Aviso: marcas de corte não detectadas na capa", 1.0)
    else:
        on_progress("Sem capa neste pack", 1.0)
