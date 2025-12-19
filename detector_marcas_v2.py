"""
Detector de Capa COM ORELHAS v3.0
Estrutura esperada: Orelha Esq | 4ª Capa | Lombada | Capa | Orelha Dir

Usa TrimBox para Y e marcas verticais para X
"""
import os
import fitz
import cv2
import numpy as np

INPUT_DIR = "./entrada"
OUTPUT_DIR = "./saida_detector_v3"
MM_TO_PT = 2.83465

def garantir_pasta(pasta):
    if not os.path.exists(pasta): os.makedirs(pasta)

def agrupar(lista, tol=5.0):
    if not lista: return []
    lista = sorted(lista)
    grupos = []
    atual = [lista[0]]
    for x in lista[1:]:
        if x - atual[-1] <= tol:
            atual.append(x)
        else:
            grupos.append(sum(atual)/len(atual))
            atual = [x]
    grupos.append(sum(atual)/len(atual))
    return grupos

def detectar_colunas_vetorial(page):
    """Detecta todas as marcas verticais nas bordas"""
    paths = page.get_drawings()
    MARGEM_Y = 100
    
    linhas_x = []
    for p in paths:
        r = p['rect']
        w = r.width
        h = r.height
        
        # Linha vertical: alta e fina
        if h > 8 and w < 6:
            no_topo = r.y0 < MARGEM_Y
            na_base = r.y1 > (page.rect.height - MARGEM_Y)
            
            if no_topo or na_base:
                linhas_x.append(r.x0 + w/2)
    
    return agrupar(linhas_x)

def identificar_estrutura(colunas, trimbox, page_width):
    """
    Identifica a estrutura da capa baseado nas colunas detectadas.
    Retorna dicionário com as coordenadas de cada parte.
    """
    resultado = {
        'orelha_esq': None,
        'quarta_capa': None,
        'lombada': None,
        'capa': None,
        'orelha_dir': None
    }
    
    if len(colunas) < 2:
        return resultado
    
    # Adiciona as bordas do TrimBox se as marcas não incluem elas
    x_inicio = trimbox.x0
    x_fim = trimbox.x1
    
    if abs(colunas[0] - x_inicio) > 50:
        colunas = [x_inicio] + colunas
    
    if abs(colunas[-1] - x_fim) > 50:
        colunas = colunas + [x_fim]
    
    print(f"\nColunas (incluindo bordas TrimBox): {len(colunas)}")
    for i, x in enumerate(colunas):
        print(f"  {i+1}: {x:.1f}pt ({x/MM_TO_PT:.1f}mm)")
    
    # Calcula intervalos
    intervalos = []
    for i in range(len(colunas) - 1):
        largura = colunas[i+1] - colunas[i]
        intervalos.append({
            'idx': i,
            'de': colunas[i],
            'ate': colunas[i+1],
            'largura': largura,
            'largura_mm': largura / MM_TO_PT
        })
    
    print(f"\nIntervalos:")
    for intv in intervalos:
        print(f"  {intv['idx']+1}: {intv['largura_mm']:.1f}mm")
    
    # NOVA LÓGICA: Agrupa intervalos pequenos consecutivos como lombada
    # Intervalos < 30mm próximos ao centro são considerados lombada
    LIMITE_LOMBADA_MM = 30  # Intervalos menores que isso podem ser lombada
    centro_pagina = page_width / 2
    
    # Encontra grupo de intervalos pequenos consecutivos próximos do centro
    lombada_inicio_idx = None
    lombada_fim_idx = None
    
    for i, intv in enumerate(intervalos):
        centro_intv = (intv['de'] + intv['ate']) / 2
        # Se está próximo do centro e é pequeno
        if abs(centro_intv - centro_pagina) < page_width * 0.25 and intv['largura_mm'] < LIMITE_LOMBADA_MM:
            if lombada_inicio_idx is None:
                lombada_inicio_idx = i
            lombada_fim_idx = i
    
    if lombada_inicio_idx is not None:
        # Lombada vai do início do primeiro intervalo pequeno até o fim do último
        lombada_x0 = colunas[lombada_inicio_idx]
        lombada_x1 = colunas[lombada_fim_idx + 1]
        largura_lombada_mm = (lombada_x1 - lombada_x0) / MM_TO_PT
        
        print(f"\nLombada identificada: Intervalos {lombada_inicio_idx+1} a {lombada_fim_idx+1}")
        print(f"  De X={lombada_x0:.1f}pt a X={lombada_x1:.1f}pt ({largura_lombada_mm:.1f}mm)")
        
        resultado['lombada'] = (lombada_x0, lombada_x1)
        
        # 4ª Capa: intervalo imediatamente antes da lombada
        if lombada_inicio_idx > 0:
            resultado['quarta_capa'] = (colunas[lombada_inicio_idx - 1], colunas[lombada_inicio_idx])
            
            # Orelha esquerda: do início até antes da 4ª capa
            if lombada_inicio_idx > 1:
                resultado['orelha_esq'] = (colunas[0], colunas[lombada_inicio_idx - 1])
        
        # Capa: intervalo imediatamente depois da lombada
        if lombada_fim_idx + 2 <= len(colunas) - 1:
            resultado['capa'] = (colunas[lombada_fim_idx + 1], colunas[lombada_fim_idx + 2])
            
            # Orelha direita: do fim da capa até o final
            if lombada_fim_idx + 3 <= len(colunas) - 1:
                resultado['orelha_dir'] = (colunas[lombada_fim_idx + 2], colunas[-1])
    
    return resultado

def gerar_debug(page, estrutura, y_top, y_bottom, path_out):
    """Gera imagem de debug com retângulos coloridos"""
    pix = page.get_pixmap(dpi=150)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).copy()
    img = img_data.reshape(pix.h, pix.w, pix.n)
    if pix.n >= 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    sx = pix.w / page.rect.width
    sy = pix.h / page.rect.height
    
    cores = {
        'orelha_esq': (100, 100, 255),   # Roxo
        'quarta_capa': (255, 100, 100),  # Azul
        'lombada': (0, 255, 255),        # Amarelo (Ciano em BGR->RGB)
        'capa': (100, 255, 100),         # Verde
        'orelha_dir': (255, 100, 255),   # Magenta
    }
    
    labels = {
        'orelha_esq': 'ORELHA ESQ',
        'quarta_capa': '4a CAPA',
        'lombada': 'LOMBADA',
        'capa': 'CAPA',
        'orelha_dir': 'ORELHA DIR',
    }
    
    for nome, coords in estrutura.items():
        if coords:
            x0, x1 = coords
            cor = cores.get(nome, (255, 255, 255))
            
            pt1 = (int(x0 * sx), int(y_top * sy))
            pt2 = (int(x1 * sx), int(y_bottom * sy))
            
            cv2.rectangle(img, pt1, pt2, cor, 4)
            
            # Label
            label = labels.get(nome, nome)
            cv2.putText(img, label, (pt1[0] + 10, pt1[1] + 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.2, cor, 3)
    
    cv2.imwrite(path_out, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

def main():
    print("--- DETECTOR DE CAPA COM ORELHAS v3.0 ---")
    garantir_pasta(OUTPUT_DIR)
    
    arquivos = os.listdir(INPUT_DIR)
    arquivo = next((f for f in arquivos if f.endswith('.pdf')), None)
    if not arquivo:
        print("Nenhum PDF encontrado")
        return
    
    doc = fitz.open(os.path.join(INPUT_DIR, arquivo))
    page = doc[0]
    
    print(f"\nArquivo: {arquivo}")
    print(f"Página: {page.rect.width:.1f}pt x {page.rect.height:.1f}pt")
    
    # Obtém TrimBox para Y
    trimbox = page.trimbox
    y_top = trimbox.y0
    y_bottom = trimbox.y1
    
    print(f"\nTrimBox: {trimbox}")
    print(f"  Y corte: {y_top:.1f} a {y_bottom:.1f}pt")
    
    # Detecta colunas via vetores
    colunas = detectar_colunas_vetorial(page)
    print(f"\nColunas detectadas: {len(colunas)}")
    
    # Identifica estrutura
    estrutura = identificar_estrutura(colunas, trimbox, page.rect.width)
    
    # Mostra resultado
    print(f"\n{'='*60}")
    print("ESTRUTURA FINAL:")
    print('='*60)
    
    for nome, coords in estrutura.items():
        if coords:
            x0, x1 = coords
            largura_mm = (x1 - x0) / MM_TO_PT
            print(f"  {nome:15}: X = {x0:7.1f} a {x1:7.1f}pt ({largura_mm:6.1f}mm)")
    
    # Exporta imagens
    for nome, coords in estrutura.items():
        if coords:
            x0, x1 = coords
            rect = fitz.Rect(x0, y_top, x1, y_bottom)
            pix = page.get_pixmap(clip=rect, dpi=300)
            pix.save(os.path.join(OUTPUT_DIR, f"_{nome}.png"))
            print(f"\n[EXPORTADO] _{nome}.png")
    
    # Gera debug
    gerar_debug(page, estrutura, y_top, y_bottom, 
                os.path.join(OUTPUT_DIR, "DEBUG_V3.png"))
    print(f"\nDebug salvo: DEBUG_V3.png")
    
    doc.close()

if __name__ == "__main__":
    main()
