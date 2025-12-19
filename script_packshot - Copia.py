import os
import shutil
import fitz
import requests
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import random

# --- CONFIGURAÇÕES GERAIS ---
INPUT_DIR = "./entrada"
OUTPUT_DIR = "./saida"

# --- CONFIGURAÇÕES DO LM STUDIO ---
LOCAL_AI_URL = "http://localhost:1234/v1/chat/completions"
AI_MODEL = "local-model"

# --- CONFIGURAÇÕES DE CORTE (MIOLO) ---
# Conversão: 1mm = 2.83465 pontos do PDF
MM_TO_PT = 2.83465

# Defina aqui quanto cortar de margem para eliminar as marcas de corte
MARGEM_CORTE_MM = 10.3 

# Prompt para a IA (Sumário)
SYSTEM_PROMPT = """
Sua tarefa é receber um texto de sumário, enviado pelo usuário. O sumário poderá ou não ter tags html e você deve extrair apenas seções que sejam **partes** ou **capítulo de hierarquia principal** e passar para uma outra estrutura de tags. O Resultado final deverá ser em uma linha. Responda apenas o resultado.

**Exemplo de entrada 1:**
<p class="SUM_Cap"><span class="_Cap"><a class="TitNum_Cor" href="cap_001.xhtml">Capítulo I</a></span></p>
<p class="SUM_Cap2"><strong class="Bold_Compressed"><a class="Tit" href="cap_001.xhtml">TENDÊNCIAS PARA A FORMAÇÃO MÉDICA NO SÉCULO XXI</a></strong></p>
<p class="SUM_Autor">DANNIELLE FERNANDES GODOI, ALEXANDRE SIZILIO</p>
<p class="SUM_Cap"><span class="_Cap"><a class="TitNum_Cor" href="cap_002.xhtml">Capítulo II</a></span></p>
<p class="SUM_Cap2"><strong class="Bold_Compressed"><a class="Tit" href="cap_002.xhtml">O PAPEL DA MEDICINA DE FAMÍLIA E COMUNIDADE NA FORMAÇÃO DO MÉDICO</a></strong></p>

**Exemplo de saída 1:**
<p><b>Capítulo I</b> - TENDÊNCIAS PARA A FORMAÇÃO MÉDICA NO SÉCULO XXI<br /><b>Capítulo II</b> - O PAPEL DA MEDICINA DE FAMÍLIA E COMUNIDADE NA FORMAÇÃO DO MÉDICO</p>

**Exemplo de entrada 2:**
Introdução
1 ◼ Solidão
2 ◼ Vivendo com... o outro

**Exemplo de saída 2:**
<p><b>Capítulo 1</b> - Solidão<br /><b>Capítulo 2</b> - Vivendo com... o outro</p>

**Exemplo de entrada 3:**
Parte I Fundamentos
1 Hello, World!
1.1 Programas
Parte II Entrada e saída
9 Fluxos de entrada e saída

**Exemplo de saída 3:**
<p><b>Parte I </b> - Fundamentos<br /><b>Capítulo 1</b> - Hello, World!</p><p><b>Parte II </b> - Fundamentos<br /><b>Capítulo 9</b> - Fluxos de entrada e saída</p>

Observação: O texto de entrada pode conter números de página ou pontilhados (....). Ignore-os e foque apenas no título do capítulo e na numeração hierárquica. Se houver, inserir também apêndices e glossários, se houver capítulos antes da parte 1, também inserir.
"""

def garantir_pasta(pasta):
    if not os.path.exists(pasta):
        os.makedirs(pasta)

# --- FUNÇÕES DE PROCESSAMENTO ---

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
        page = pdf_ensaio[-1] # Pega a página recém inserida
        
        # Aplica o corte (CropBox) reduzindo as margens
        r = page.rect
        novo_rect = fitz.Rect(
            r.x0 + margem_pt, # Esquerda
            r.y0 + margem_pt, # Topo
            r.x1 - margem_pt, # Direita
            r.y1 - margem_pt  # Base
        )
        page.set_cropbox(novo_rect)
    
    path_ensaio = os.path.join(output_folder, f"{isbn}_ensaiodeleitura.pdf")
    pdf_ensaio.save(path_ensaio)
    print(f"   [OK] PDF Ensaio salvo (Corte aplicado de {MARGEM_CORTE_MM}mm).")
    
    # 2. GERA AS IMAGENS DE VITRINE (_vi_)
    # Lógica: Página 1 fixa + 3 Aleatórias
    doc_vi = fitz.open(path_ensaio)
    total_paginas = len(doc_vi)
    
    indices_para_exportar = []
    
    if total_paginas > 0:
        indices_para_exportar.append(0) # Sempre a primeira
        
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

# --- FUNÇÕES AUXILIARES ---

def chamar_ia_local(texto_sumario):
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
        response = requests.post(LOCAL_AI_URL, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if 'choices' in data:
                return data['choices'][0]['message']['content'].strip()
    except Exception as e:
        print(f"   [ERRO IA] {e}")
    return "<p>Erro ao processar sumário.</p>"

def extrair_toc_epub(epub_path):
    try:
        book = epub.read_epub(epub_path)
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            name = item.get_name().lower()
            if any(x in name for x in ['toc', 'sumario', 'nav', 'contents']):
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                return soup.get_text(separator='\n')
        if book.toc:
            t = ""
            for x in book.toc: t += f"{x.title if hasattr(x, 'title') else x[0].title}\n"
            return t
    except: pass
    return None

def extrair_toc_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    toc = doc.get_toc()
    if toc: return "\n".join([x[1] for x in toc])
    txt = ""
    for i in range(min(25, len(doc))):
        page_txt = doc[i].get_text()
        if any(x in page_txt.lower() for x in ['sumário', 'contents']):
            txt += page_txt
            if i+1 < len(doc): txt += doc[i+1].get_text()
            return txt
    return None

# --- MAIN ---

def main():
    print("--- INICIANDO PROCESSAMENTO (COM CÓPIA DE CAPA) ---")
    garantir_pasta(OUTPUT_DIR)
    
    arquivos = os.listdir(INPUT_DIR)
    isbns = set()
    for f in arquivos:
        if f.endswith('.pdf') and ('miolo' in f.lower() or 'interior' in f.lower()):
            isbns.add(f.split('_')[0])
    
    if not isbns:
        print("Nenhum arquivo de Miolo encontrado.")
        return

    for isbn in isbns:
        print(f"\nISBN: {isbn}")
        pasta_livro = os.path.join(OUTPUT_DIR, isbn)
        garantir_pasta(pasta_livro)
        
        # Localiza arquivos
        path_miolo = None
        path_capa = None # Variável para guardar o caminho da capa
        
        for f in arquivos:
            if f.startswith(isbn) and f.endswith(".pdf"):
                f_lower = f.lower()
                if "miolo" in f_lower or "interior" in f_lower:
                    path_miolo = os.path.join(INPUT_DIR, f)
                elif "capa" in f_lower:
                    path_capa = os.path.join(INPUT_DIR, f)
        
        path_epub = os.path.join(INPUT_DIR, f"{isbn}.epub")
        
        # Processa Miolo e Sumário
        if path_miolo:
            processar_miolo(path_miolo, path_epub, isbn, pasta_livro)
        else:
            print("   [ERRO] Arquivo de miolo não encontrado.")

        # Copia arquivo de Capa (se existir)
        if path_capa:
            nome_arquivo_capa = os.path.basename(path_capa)
            destino_capa = os.path.join(pasta_livro, nome_arquivo_capa)
            shutil.copy2(path_capa, destino_capa)
            print(f"   [OK] Arquivo original de Capa copiado para a pasta.")
        else:
            print("   [AVISO] Arquivo de Capa original não encontrado para cópia.")

if __name__ == "__main__":
    main()