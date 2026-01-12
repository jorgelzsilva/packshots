"""
Módulo de Processamento de Miolo
--------------------------------
Gera PDF de ensaio, imagens de vitrine e sumário via IA.
"""
import os
import random
import requests
import fitz
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

from config import MM_TO_PT, MARGEM_CORTE_MM, AI_URL, AI_MODEL, SYSTEM_PROMPT


def garantir_pasta(pasta):
    """Cria pasta se não existir"""
    if not os.path.exists(pasta):
        os.makedirs(pasta)


def chamar_ia_local(texto_sumario):
    """Chama a IA local para processar sumário"""
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Texto do sumário:\n{texto_sumario}"}
            ],
            "temperature": 0.1,
            "stream": False
        }
        response = requests.post(AI_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"   [ERRO IA] {e}")
    return "<p>Erro ao processar sumário.</p>"


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
                t += f"{x.title if hasattr(x, 'title') else x[0].title}\n"
            return t
    except:
        pass
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


def processar_miolo(pdf_path, epub_path, isbn, output_folder):
    """
    Gera:
    1. _ensaiodeleitura.pdf (15 págs, com corte de margem)
    2. _vi_0X.png (1ª Pág + 3 Aleatórias)
    3. _sumario.txt (via IA)
    """
    print(f"   -> Iniciando processamento do miolo...")
    doc = fitz.open(pdf_path)
    pdf_ensaio = fitz.open()
    
    # Define a margem em pontos
    margem_pt = MARGEM_CORTE_MM * MM_TO_PT
    
    # Define intervalo de páginas (0 até 15)
    start_page = 0
    end_page = min(15, len(doc))
    
    # 1. GERA O PDF DE ENSAIO (CORTADO)
    for i in range(start_page, end_page):
        pdf_ensaio.insert_pdf(doc, from_page=i, to_page=i)
        page = pdf_ensaio[-1]
        
        # Aplica o corte (CropBox)
        r = page.rect
        novo_rect = fitz.Rect(
            r.x0 + margem_pt,
            r.y0 + margem_pt,
            r.x1 - margem_pt,
            r.y1 - margem_pt
        )
        page.set_cropbox(novo_rect)
    
    path_ensaio = os.path.join(output_folder, f"{isbn}_ensaiodeleitura.pdf")
    pdf_ensaio.save(path_ensaio)
    print(f"   [OK] PDF Ensaio salvo (Corte aplicado de {MARGEM_CORTE_MM}mm).")
    
    # 2. GERA AS IMAGENS DE VITRINE (_vi_)
    doc_vi = fitz.open(path_ensaio)
    total_paginas = len(doc_vi)
    
    indices_para_exportar = []
    
    if total_paginas > 0:
        indices_para_exportar.append(0)
        
        paginas_restantes = list(range(1, total_paginas))
        if paginas_restantes:
            qtd_sorteio = min(3, len(paginas_restantes))
            sorteadas = random.sample(paginas_restantes, qtd_sorteio)
            indices_para_exportar.extend(sorted(sorteadas))
    
    for i, page_idx in enumerate(indices_para_exportar):
        pix = doc_vi[page_idx].get_pixmap(dpi=150)
        pix.save(os.path.join(output_folder, f"{isbn}_vi_0{i+1}.png"))
        
    print(f"   [OK] Imagens de vitrine geradas (1ª Fixa + {len(indices_para_exportar)-1} Aleatórias).")
    
    # 3. GERA O SUMÁRIO (IA)
    raw_toc = None
    if epub_path and os.path.exists(epub_path):
        raw_toc = extrair_toc_epub(epub_path)
        
    if not raw_toc:
        raw_toc = extrair_toc_pdf(pdf_path)
        
    if raw_toc:
        print(f"   -> Sumário encontrado ({len(raw_toc)} caracteres). Enviando para a IA processar...")
        html_final = chamar_ia_local(raw_toc)
        with open(os.path.join(output_folder, f"{isbn}_sumario.txt"), "w", encoding="utf-8") as f:
            f.write(html_final)
        print(f"   [OK] Sumário processado via IA.")
    else:
        print(f"   [FALHA] Sumário não encontrado automaticamente.")
    
    doc.close()
    doc_vi.close()
    pdf_ensaio.close()
