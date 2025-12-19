import os
import fitz  # PyMuPDF
import cv2
import numpy as np

# --- CONFIGURAÇÕES ---
INPUT_DIR = "./entrada"
OUTPUT_DIR = "./saida_teste_capa"
MM_TO_PT = 2.83465
TARGET_CROP_MM = 15.0  # Alvo de altura

def garantir_pasta(pasta):
    if not os.path.exists(pasta): os.makedirs(pasta)

def agrupar(lista, tol=2.0):
    if not lista: return []
    lista.sort()
    grupos = []
    atual = [lista[0]]
    for x in lista[1:]:
        if x - atual[-1] <= tol: atual.append(x)
        else:
            grupos.append(sum(atual)/len(atual))
            atual = [x]
    grupos.append(sum(atual)/len(atual))
    return grupos

def detectar_grade_v10(page):
    paths = page.get_drawings()
    
    # Listas temporárias
    v_candidates = [] # Tuplas (x0, y0)
    h_candidates = [] # Apenas y0
    
    W = page.rect.width
    H = page.rect.height
    
    # Limites de Varredura (O "L" Scanner)
    SCAN_DEPTH_TOPO = 100  # Só olha os primeiros 100pts verticais para achar X
    SCAN_DEPTH_ESQ = 100   # Só olha os primeiros 100pts horizontais para achar Y
    
    print(f"--- SCANNING V10 (TOP-FIRST + 15MM) ---")
    
    for p in paths:
        r = p['rect']
        w = r.width
        h = r.height
        
        # 1. VERTICAIS (Para Largura) - Só no topo
        if h > 10 and w < 5:
            if r.y0 < SCAN_DEPTH_TOPO:
                v_candidates.append((r.x0, r.y0))
                
        # 2. HORIZONTAIS (Para Altura) - Só na esquerda
        elif w > 10 and h < 5:
            if r.x0 < SCAN_DEPTH_ESQ:
                h_candidates.append(r.y0)

    # --- PROCESSAMENTO X (LARGURA) ---
    # Lógica: "Encontrar o primeiro item no eixo Y"
    # Pegamos o MENOR y0 encontrado entre todas as linhas verticais.
    # Só aceitamos linhas que começam nesse mesmo nível (tolerância 1pt).
    cols = []
    if v_candidates:
        min_y = min([item[1] for item in v_candidates])
        print(f"   -> Topo das marcas verticais encontrado em Y={min_y:.2f}")
        
        # Filtra: Aceita apenas quem começa no topo absoluto
        # A cruz de registro começa mais baixo, então será excluída aqui.
        v_filtered = [item[0] for item in v_candidates if abs(item[1] - min_y) < 2.0]
        cols = agrupar(v_filtered)
        print(f"   -> Linhas verticais válidas: {len(cols)} (Cruz removida)")

    # --- PROCESSAMENTO Y (ALTURA) ---
    # Lógica: Proximidade de 15mm
    target_top = TARGET_CROP_MM * MM_TO_PT
    target_bottom = H - (TARGET_CROP_MM * MM_TO_PT)
    tol = 5.0 * MM_TO_PT # +/- 5mm de tolerância
    
    # Acha a melhor linha de topo
    best_top = None
    min_dist = float('inf')
    for y in h_candidates:
        dist = abs(y - target_top)
        if dist < tol and dist < min_dist:
            min_dist = dist
            best_top = y
            
    # Acha a melhor linha de base
    best_bottom = None
    min_dist = float('inf')
    for y in h_candidates:
        dist = abs(y - target_bottom)
        if dist < tol and dist < min_dist:
            min_dist = dist
            best_bottom = y
            
    # Fallback se não achar linha vetorial exata
    if best_top is None: best_top = target_top
    if best_bottom is None: best_bottom = target_bottom

    return cols, best_top, best_bottom

def gerar_debug(page, cols, y_top, y_bottom, x_lombada_esq, x_lombada_dir, rect_capa, rect_quarta, path_out):
    pix = page.get_pixmap(dpi=150)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).copy()
    img = img_data.reshape(pix.h, pix.w, pix.n)
    if pix.n >= 4: img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    sx = pix.w / page.rect.width
    sy = pix.h / page.rect.height
    
    # Linhas de Referencia 15mm (Amarelo)
    tt = int(15 * MM_TO_PT * sy)
    tb = int((page.rect.height - 15 * MM_TO_PT) * sy)
    cv2.line(img, (0, tt), (pix.w, tt), (0, 255, 255), 1)
    cv2.line(img, (0, tb), (pix.w, tb), (0, 255, 255), 1)

    # Verticais Detectadas (Verde)
    for x in cols:
        cv2.line(img, (int(x*sx), 0), (int(x*sx), pix.h), (0, 255, 0), 1)

    # Lombada (Verde Neon)
    if x_lombada_esq: cv2.line(img, (int(x_lombada_esq*sx), 0), (int(x_lombada_esq*sx), pix.h), (0, 255, 128), 4)
    if x_lombada_dir: cv2.line(img, (int(x_lombada_dir*sx), 0), (int(x_lombada_dir*sx), pix.h), (0, 255, 128), 4)

    # Alturas (Azul)
    if y_top: cv2.line(img, (0, int(y_top*sy)), (pix.w, int(y_top*sy)), (255, 255, 0), 2)
    if y_bottom: cv2.line(img, (0, int(y_bottom*sy)), (pix.w, int(y_bottom*sy)), (255, 255, 0), 2)

    # Caixas Finais (Vermelho)
    if rect_capa:
        cv2.rectangle(img, (int(rect_capa.x0*sx), int(rect_capa.y0*sy)), (int(rect_capa.x1*sx), int(rect_capa.y1*sy)), (0, 0, 255), 3)
    if rect_quarta:
        cv2.rectangle(img, (int(rect_quarta.x0*sx), int(rect_quarta.y0*sy)), (int(rect_quarta.x1*sx), int(rect_quarta.y1*sy)), (0, 0, 255), 3)

    cv2.imwrite(path_out, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

def main():
    print("--- TESTE CAPA V10 (FINAL) ---")
    garantir_pasta(OUTPUT_DIR)
    
    arquivos = os.listdir(INPUT_DIR)
    arquivo_capa = next((f for f in arquivos if f.endswith('.pdf') and 'capa' in f.lower()), None)
    if not arquivo_capa: return

    path = os.path.join(INPUT_DIR, arquivo_capa)
    doc = fitz.open(path)
    page = doc[0]
    
    # 1. Detecção V10
    cols, y_cut_top, y_cut_bottom = detectar_grade_v10(page)
    
    rect_capa = None
    rect_quarta = None
    x_lombada_esq = None
    x_lombada_dir = None
    
    # 2. Definição da Lombada (Eixo X)
    if len(cols) >= 3:
        meio_pagina = page.rect.width / 2
        # Procura as duas linhas mais próximas do centro
        candidatos_lombada = [x for x in cols if abs(x - meio_pagina) < 100]
        
        if len(candidatos_lombada) >= 2:
            x_lombada_esq = min(candidatos_lombada)
            x_lombada_dir = max(candidatos_lombada)
            
            # --- Definição das Abas ---
            # Capa (Direita da Lombada)
            # Acha a primeira linha à direita da lombada
            linhas_dir = [x for x in cols if x > x_lombada_dir + 10]
            if linhas_dir:
                x_fim_capa = linhas_dir[0] # A primeira linha é o fim da capa
            else:
                x_fim_capa = page.rect.width # Fallback
                
            # Quarta Capa (Esquerda da Lombada)
            # Acha a última linha à esquerda da lombada
            linhas_esq = [x for x in cols if x < x_lombada_esq - 10]
            if linhas_esq:
                x_inicio_quarta = linhas_esq[-1] # A última linha é o início da quarta capa
            else:
                x_inicio_quarta = 0 # Fallback
            
            # Monta Retângulos
            rect_capa = fitz.Rect(x_lombada_dir, y_cut_top, x_fim_capa, y_cut_bottom)
            rect_quarta = fitz.Rect(x_inicio_quarta, y_cut_top, x_lombada_esq, y_cut_bottom)
            
            print(f"[SUCESSO] Capa: {rect_capa}")
            
            # Salva Imagens
            page.get_pixmap(clip=rect_capa, dpi=300).save(os.path.join(OUTPUT_DIR, "_capa_v10.png"))
            page.get_pixmap(clip=rect_quarta, dpi=300).save(os.path.join(OUTPUT_DIR, "_quartacapa_v10.png"))

        else:
            print("[FALHA] Não foi possível definir a lombada (linhas insuficientes no centro).")
    else:
        print("[FALHA] Menos de 3 linhas verticais detectadas.")

    path_debug = os.path.join(OUTPUT_DIR, "DEBUG_V10.png")
    gerar_debug(page, cols, y_cut_top, y_cut_bottom, x_lombada_esq, x_lombada_dir, rect_capa, rect_quarta, path_debug)
    print(f"Debug salvo: {path_debug}")

if __name__ == "__main__":
    main()