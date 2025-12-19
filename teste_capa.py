import os
import fitz  # PyMuPDF
import cv2
import numpy as np

# --- CONFIG ---
INPUT_DIR = "./entrada"
OUTPUT_DIR = "./saida_teste_capa"
MM_TO_PT = 2.83465
TARGET_CROP_MM = 15.0

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

# ==============================================================================
# 1. LARGURA (X) - VETOR TOPO (Mantido)
# ==============================================================================
def detectar_largura_vetorial(page):
    paths = page.get_drawings()
    v_candidates = []
    SCAN_DEPTH_TOPO = 100 
    
    for p in paths:
        r = p['rect']
        w = r.width
        h = r.height
        if h > 10 and w < 5:
            if r.y0 < SCAN_DEPTH_TOPO:
                v_candidates.append((r.x0, r.y0))
                
    cols = []
    if v_candidates:
        min_y = min([item[1] for item in v_candidates])
        v_filtered = [item[0] for item in v_candidates if abs(item[1] - min_y) < 2.0]
        cols = agrupar(v_filtered)
    return cols

# ==============================================================================
# 2. ALTURA (Y) - DARK GRAY + ORDENAÇÃO
# ==============================================================================
def detectar_altura_dark_gray(page):
    print("   -> Scanner V18: Dark Gray (RGB 47) + Ordenação Pura...")
    
    # 1. Scanner 300 DPI
    WIDTH_SCAN_MM = 50 # Escaneia uma faixa larga (50mm) para garantir que pega o início
    width_pt = WIDTH_SCAN_MM * MM_TO_PT
    clip_rect = fitz.Rect(0, 0, width_pt, page.rect.height)
    pix = page.get_pixmap(clip=clip_rect, dpi=300)
    
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).copy()
    img = img_data.reshape(pix.h, pix.w, pix.n)
    if pix.n >= 4: img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    # 2. Converte para Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    
    # 3. THRESHOLD AJUSTADO PARA CINZA ESCURO
    # Inverte: Tinta (0 a ~200) vira BRANCO (255). Papel (200-255) vira PRETO (0).
    # O valor 200 é seguro: pega preto (0), cinza escuro (47) e até cinza médio (150).
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # 4. FILTRO DE LINHA HORIZONTAL
    # Usa um kernel longo para destruir texto e ruído, mantendo só linhas.
    # Em 300 DPI, 40 pixels é aprox 3.3mm. Suficiente para identificar um traço.
    kernel_line = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))
    
    # Erode (remove ruído) -> Dilate (restaura tamanho)
    morph = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_line)
    
    # 5. Contornos
    contours, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    scale_y = page.rect.height / pix.h
    scale_x = page.rect.width / pix.w
    
    candidates_top = []
    candidates_bottom = []
    
    height_px = pix.h
    zm_y0 = height_px * 0.25
    zm_y1 = height_px * 0.75
    
    # Imagem de Debug (para vermos o que ele detectou)
    debug_mask = cv2.cvtColor(morph, cv2.COLOR_GRAY2BGR)
    # Escurece tudo para destacar os vencedores depois
    debug_mask[np.where((debug_mask==[255,255,255]).all(axis=2))] = [60,60,60] 

    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        
        # Filtro de Largura Mínima: A linha tem que ter pelo menos uns 30px (2.5mm)
        if w > 30:
            y_centro_px = y + (h/2)
            y_pt = y_centro_px * scale_y
            x_pt = x * scale_x
            
            cand = {'x': x_pt, 'y': y_pt, 'cnt': cnt}
            
            # Classifica Topo vs Base
            if y_centro_px < zm_y0:
                candidates_top.append(cand)
            elif y_centro_px > zm_y1:
                candidates_bottom.append(cand)

    # 6. ORDENAÇÃO (SEM FILTRO DE X MÍNIMO)
    # Simplesmente pegamos a linha que tiver o MENOR X em cada grupo.
    
    best_top = None
    if candidates_top:
        # Ordena: Menor X primeiro (mais à esquerda)
        candidates_top.sort(key=lambda k: k['x'])
        winner = candidates_top[0]
        best_top = winner['y']
        
        print(f"   [TOPO] Vencedor: X={winner['x']:.1f}pt | Y={best_top:.1f}pt")
        # Pinta Vencedor de Ciano
        cv2.drawContours(debug_mask, [winner['cnt']], -1, (255, 255, 0), 3)
        # Pinta os outros de Vermelho
        for c in candidates_top[1:]:
             cv2.drawContours(debug_mask, [c['cnt']], -1, (0, 0, 255), 1)

    best_bottom = None
    if candidates_bottom:
        candidates_bottom.sort(key=lambda k: k['x'])
        winner = candidates_bottom[0]
        best_bottom = winner['y']
        
        print(f"   [BASE] Vencedor: X={winner['x']:.1f}pt | Y={best_bottom:.1f}pt")
        cv2.drawContours(debug_mask, [winner['cnt']], -1, (255, 255, 0), 3)
        for c in candidates_bottom[1:]:
             cv2.drawContours(debug_mask, [c['cnt']], -1, (0, 0, 255), 1)

    # Fallbacks (se não achou NADA)
    if best_top is None: 
        best_top = TARGET_CROP_MM * MM_TO_PT
        print("   [AVISO] Nenhuma linha no topo. Usando 15mm.")
    if best_bottom is None: 
        best_bottom = page.rect.height - (TARGET_CROP_MM * MM_TO_PT)
        print("   [AVISO] Nenhuma linha na base. Usando 15mm.")

    return best_top, best_bottom, debug_mask

# ==============================================================================
# DEBUGGER
# ==============================================================================
def gerar_debug(page, cols, y_top, y_bottom, x_lombada_esq, x_lombada_dir, rect_capa, rect_quarta, img_mask_color, path_out):
    pix = page.get_pixmap(dpi=300)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).copy()
    img = img_data.reshape(pix.h, pix.w, pix.n)
    if pix.n >= 4: img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    sx = pix.w / page.rect.width
    sy = pix.h / page.rect.height
    
    # Overlay Visual
    h_vis, w_vis = img_mask_color.shape[:2]
    roi = img[0:h_vis, 0:w_vis]
    mask_indices = np.any(img_mask_color != [0,0,0], axis=-1)
    roi[mask_indices] = img_mask_color[mask_indices]
    img[0:h_vis, 0:w_vis] = roi

    # Linhas
    for x in cols: cv2.line(img, (int(x*sx), 0), (int(x*sx), pix.h), (0, 255, 0), 2)
    if x_lombada_esq: cv2.line(img, (int(x_lombada_esq*sx), 0), (int(x_lombada_esq*sx), pix.h), (0, 255, 128), 6)
    if x_lombada_dir: cv2.line(img, (int(x_lombada_dir*sx), 0), (int(x_lombada_dir*sx), pix.h), (0, 255, 128), 6)

    if y_top: cv2.line(img, (0, int(y_top*sy)), (pix.w, int(y_top*sy)), (255, 255, 0), 4)
    if y_bottom: cv2.line(img, (0, int(y_bottom*sy)), (pix.w, int(y_bottom*sy)), (255, 255, 0), 4)

    # Retângulos
    if rect_capa:
        cv2.rectangle(img, (int(rect_capa.x0*sx), int(rect_capa.y0*sy)), (int(rect_capa.x1*sx), int(rect_capa.y1*sy)), (0, 0, 255), 5)
    if rect_quarta:
        cv2.rectangle(img, (int(rect_quarta.x0*sx), int(rect_quarta.y0*sy)), (int(rect_quarta.x1*sx), int(rect_quarta.y1*sy)), (0, 0, 255), 5)

    cv2.imwrite(path_out, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

def main():
    print("--- TESTE CAPA V18 (DARK GRAY + SORT BY X) ---")
    garantir_pasta(OUTPUT_DIR)
    
    arquivos = os.listdir(INPUT_DIR)
    arquivo_capa = next((f for f in arquivos if f.endswith('.pdf') and 'capa' in f.lower()), None)
    if not arquivo_capa: return

    path = os.path.join(INPUT_DIR, arquivo_capa)
    doc = fitz.open(path)
    page = doc[0]
    
    cols = detectar_largura_vetorial(page)
    y_cut_top, y_cut_bottom, img_mask_color = detectar_altura_dark_gray(page)
    
    rect_capa = None
    rect_quarta = None
    x_lombada_esq = None
    x_lombada_dir = None
    
    if len(cols) >= 3:
        meio_pagina = page.rect.width / 2
        candidatos_lombada = [x for x in cols if abs(x - meio_pagina) < 100]
        
        if len(candidatos_lombada) >= 2:
            x_lombada_esq = min(candidatos_lombada)
            x_lombada_dir = max(candidatos_lombada)
            
            linhas_dir = [x for x in cols if x > x_lombada_dir + 10]
            x_fim_capa = linhas_dir[0] if linhas_dir else page.rect.width
            
            linhas_esq = [x for x in cols if x < x_lombada_esq - 10]
            x_inicio_quarta = linhas_esq[-1] if linhas_esq else 0
            
            rect_capa = fitz.Rect(x_lombada_dir, y_cut_top, x_fim_capa, y_cut_bottom)
            rect_quarta = fitz.Rect(x_inicio_quarta, y_cut_top, x_lombada_esq, y_cut_bottom)
            
            print(f"[SUCESSO] Capa: {rect_capa}")
            page.get_pixmap(clip=rect_capa, dpi=300).save(os.path.join(OUTPUT_DIR, "_capa_v18.png"))
            page.get_pixmap(clip=rect_quarta, dpi=300).save(os.path.join(OUTPUT_DIR, "_quartacapa_v18.png"))
        else:
            print("[FALHA] Lombada não encontrada.")
            
    path_debug = os.path.join(OUTPUT_DIR, "DEBUG_V18.png")
    gerar_debug(page, cols, y_cut_top, y_cut_bottom, x_lombada_esq, x_lombada_dir, rect_capa, rect_quarta, img_mask_color, path_debug)
    print(f"Debug salvo: {path_debug}")

if __name__ == "__main__":
    main()