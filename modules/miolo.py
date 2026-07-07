"""
Módulo de Processamento de Miolo
--------------------------------
Gera PDF de ensaio, imagens de vitrine e sumário via IA.

As três etapas são expostas como funções independentes
(gerar_ensaio / gerar_vitrines / gerar_sumario) para que a Web UI
possa gerar — e reprocessar — cada artefato isoladamente.
"""
import os
import time
import random
import requests
import fitz
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from config import (MM_TO_PT, MARGEM_CORTE_MM, AI_URL, AI_MODEL, AI_FALLBACK_MODELS,
                    AI_API_KEY, SYSTEM_PROMPT, EXPORT_PNG_WIDTH)
from modules.utils import salvar_png_redimensionado, garantir_pasta

# Rodadas sobre toda a lista de modelos (com backoff entre rodadas)
IA_RODADAS = 2


def _tentar_modelo_ia(model, texto_sumario):
    """Uma tentativa única com um modelo. Retorna o texto ou lança exceção."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AI_API_KEY}",
        "HTTP-Referer": "https://github.com/jorgelzsilva/packshots",  # Recomendado pela OpenRouter
        "X-Title": "Packshots Auto"                                  # Recomendado pela OpenRouter
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Texto do sumário:\n{texto_sumario}"}
        ],
        "temperature": 0.1,
        "stream": False
    }
    response = requests.post(AI_URL, headers=headers, json=payload, timeout=60)
    if response.status_code == 429 or response.status_code >= 500:
        raise RuntimeError(f"provedor indisponível (HTTP {response.status_code})")
    response.raise_for_status()
    data = response.json()
    if 'choices' in data and data['choices']:
        return data['choices'][0]['message']['content'].strip()
    raise RuntimeError("resposta sem conteúdo")


def chamar_ia_local(texto_sumario, model=None):
    """
    Chama a IA para processar o sumário, com cadeia de modelos alternativos.

    Se `model` for informado, ele é tentado primeiro; caso contrário usa o
    modelo principal (AI_MODEL). Em qualquer caso, os demais modelos servem
    de reserva, na ordem. Como o 429 do pool gratuito costuma ser transitório,
    faz algumas rodadas com backoff. Lança exceção se todos falharem.
    """
    if model:
        candidatos = [model] + [AI_MODEL] + list(AI_FALLBACK_MODELS)
    else:
        candidatos = [AI_MODEL] + list(AI_FALLBACK_MODELS)

    # Remove duplicados preservando a ordem
    modelos = []
    for m in candidatos:
        if m and m not in modelos:
            modelos.append(m)

    ultimo_erro = "Falha desconhecida na IA."

    for rodada in range(IA_RODADAS):
        for model in modelos:
            try:
                resultado = _tentar_modelo_ia(model, texto_sumario)
                if model != AI_MODEL:
                    print(f"   [IA] Sumário gerado pelo modelo alternativo: {model}")
                return resultado
            except requests.Timeout:
                ultimo_erro = f"{model}: tempo esgotado"
            except requests.RequestException as e:
                ultimo_erro = f"{model}: erro de conexão ({e})"
            except Exception as e:
                ultimo_erro = f"{model}: {e}"
            print(f"   [IA] Falhou {model}: {ultimo_erro}")

        # Todos os modelos falharam nesta rodada: espera antes de repetir
        if rodada < IA_RODADAS - 1:
            espera = 2 ** rodada
            print(f"   [IA] Todos os modelos falharam — nova rodada em {espera}s...")
            time.sleep(espera)

    msg = f"Todos os modelos de IA falharam ({', '.join(modelos)}). Último erro: {ultimo_erro}"
    print(f"   [ERRO IA] {msg}")
    raise RuntimeError(msg)


def extrair_toc_epub(epub_path):
    """Extrai sumário do EPUB"""
    try:
        book = epub.read_epub(epub_path)
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            name = item.get_name().lower()
            if any(x in name for x in ['toc', 'sumario', 'nav', 'contents']):
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                return soup.get_text(separator='\n')
        if book.toc:
            t = ""
            for x in book.toc:
                title = x.title if hasattr(x, 'title') else (x[0].title if isinstance(x, (list, tuple)) and hasattr(x[0], 'title') else str(x))
                t += f"{title}\n"
            return t
    except Exception as e:
        print(f"   [AVISO] Falha ao extrair TOC do EPUB: {e}")
    return None


def extrair_toc_pdf(pdf_path):
    """Extrai sumário do PDF"""
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    if toc:
        return "\n".join([x[1] for x in toc])
    txt = ""
    for i in range(min(25, len(doc))):
        page_txt = doc[i].get_text()
        if any(x in page_txt.lower() for x in ['sumário', 'contents']):
            txt += page_txt
            if i+1 < len(doc):
                txt += doc[i+1].get_text()
            return txt
    return None


def gerar_ensaio(pdf_path, ident, output_folder, on_progress=None):
    """Gera o PDF de ensaio de leitura (15 págs, com corte de margem). Retorna o caminho."""
    assert os.path.exists(pdf_path), f"Arquivo de miolo não encontrado: {pdf_path}"
    garantir_pasta(output_folder)

    doc = fitz.open(pdf_path)
    pdf_ensaio = fitz.open()
    margem_pt = MARGEM_CORTE_MM * MM_TO_PT
    start_page = 0
    end_page = min(15, len(doc))

    for i in range(start_page, end_page):
        pdf_ensaio.insert_pdf(doc, from_page=i, to_page=i)
        page = pdf_ensaio[-1]
        r = page.rect
        page.set_cropbox(fitz.Rect(r.x0 + margem_pt, r.y0 + margem_pt, r.x1 - margem_pt, r.y1 - margem_pt))
        if on_progress and end_page > start_page:
            on_progress(f"Gerando ensaio: página {i + 1}/{end_page}", (i + 1 - start_page) / (end_page - start_page))

    path_ensaio = os.path.join(output_folder, f"{ident}_ensaiodeleitura.pdf")
    pdf_ensaio.save(path_ensaio)
    doc.close()
    pdf_ensaio.close()
    print(f"   [OK] PDF Ensaio salvo (Corte aplicado de {MARGEM_CORTE_MM}mm).")
    return path_ensaio


def gerar_vitrines(ensaio_path, ident, output_folder, on_progress=None):
    """Gera as imagens de vitrine (1ª página + 3 aleatórias). Retorna lista de caminhos."""
    assert os.path.exists(ensaio_path), f"PDF de ensaio não encontrado: {ensaio_path}"
    garantir_pasta(output_folder)

    doc_vi = fitz.open(ensaio_path)
    total_paginas = len(doc_vi)

    indices = []
    if total_paginas > 0:
        indices.append(0)
        restantes = list(range(1, total_paginas))
        if restantes:
            indices.extend(sorted(random.sample(restantes, min(3, len(restantes)))))

    caminhos = []
    for i, page_idx in enumerate(indices):
        pix = doc_vi[page_idx].get_pixmap(dpi=150)
        caminho = os.path.join(output_folder, f"{ident}_vi_0{i+1}.png")
        salvar_png_redimensionado(pix, caminho, EXPORT_PNG_WIDTH)
        caminhos.append(caminho)
        if on_progress:
            on_progress(f"Gerando vitrine {i + 1}/{len(indices)}", (i + 1) / len(indices))

    doc_vi.close()
    print(f"   [OK] Imagens de vitrine geradas (1ª Fixa + {len(indices)-1} Aleatórias).")
    return caminhos


def gerar_sumario(pdf_path, epub_path, ident, output_folder, model=None):
    """
    Extrai o sumário (EPUB ou PDF) e processa via IA, gravando o .txt.

    Args:
        model: modelo de IA preferido (opcional); os demais servem de reserva.

    Returns:
        dict: {'status': 'ok'|'erro', 'sumario': caminho|None, 'error': str}
    """
    garantir_pasta(output_folder)

    raw_toc = None
    if epub_path and os.path.exists(epub_path):
        raw_toc = extrair_toc_epub(epub_path)
    if not raw_toc:
        raw_toc = extrair_toc_pdf(pdf_path)

    if not raw_toc:
        print("   [FALHA] Sumário não encontrado automaticamente.")
        return {'status': 'erro', 'sumario': None, 'error': 'Sumário não encontrado no EPUB nem no PDF.'}

    print(f"   -> Sumário encontrado ({len(raw_toc)} caracteres). Enviando para a IA processar...")
    try:
        html_final = chamar_ia_local(raw_toc, model=model)
    except Exception as e:
        return {'status': 'erro', 'sumario': None, 'error': str(e)}

    path_sumario = os.path.join(output_folder, f"{ident}_sumario.txt")
    with open(path_sumario, "w", encoding="utf-8") as f:
        f.write(html_final)
    print("   [OK] Sumário processado via IA.")
    return {'status': 'ok', 'sumario': path_sumario, 'error': ''}


def processar_miolo(pdf_path, epub_path, ident, output_folder, on_progress=None):
    """
    Fluxo completo do miolo (usado pela CLI):
    1. _ensaiodeleitura.pdf (15 págs, com corte de margem)
    2. _vi_0X.png (1ª Pág + 3 Aleatórias)
    3. _sumario.txt (via IA)

    Returns:
        dict com caminhos gerados: {'ensaio': str, 'vitrines': list[str], 'sumario': str|None}
    """
    assert os.path.exists(pdf_path), f"Arquivo de miolo não encontrado: {pdf_path}"
    print("   -> Iniciando processamento do miolo...")

    path_ensaio = gerar_ensaio(
        pdf_path, ident, output_folder,
        on_progress=(lambda m, f: on_progress(m, 0.4 * f)) if on_progress else None,
    )

    vitrines = gerar_vitrines(
        path_ensaio, ident, output_folder,
        on_progress=(lambda m, f: on_progress(m, 0.4 + 0.2 * f)) if on_progress else None,
    )

    if on_progress:
        on_progress("Processando sumário", 0.7)

    res_sumario = gerar_sumario(pdf_path, epub_path, ident, output_folder)

    if on_progress:
        on_progress("Miolo processado", 1.0)

    return {'ensaio': path_ensaio, 'vitrines': vitrines, 'sumario': res_sumario['sumario']}
