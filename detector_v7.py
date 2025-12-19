"""
Detector de Capa v7.0 - Y Mínimo EXATO
--------------------------------------
Filtra APENAS marcas com o menor Y global (marcas de corte reais)
"""
import os
import fitz
import cv2
import numpy as np

INPUT_DIR = "./entrada"
OUTPUT_DIR = "./saida_detector_v7"
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

def detectar_marcas_corte(page):
    """
    Detecta apenas as marcas de corte REAIS:
    - Linhas verticais com o menor Y0 (mais próximas do topo absoluto)
    - Tolerância de 2pt para o Y mínimo
    """
    paths = page.get_drawings()
    
    linhas = []
    for p in paths:
        r = p['rect']
        w = r.width
        h = r.height
        
        # Linha vertical: alta (>8pt) e fina (<6pt)
        if h > 8 and w < 6:
            linhas.append({
                'x': r.x0 + w/2,
                'y0': r.y0,
                'h': h
            })
    
    if not linhas:
        return []
    
    # FILTRA: ignora marcas com Y negativo (fora da página)
    linhas_validas = [l for l in linhas if l['y0'] >= 0]
    
    if not linhas_validas:
        print("⚠ Nenhuma marca com Y >= 0 encontrada")
        return []
    
    # Encontra o Y mínimo global (apenas de marcas válidas)
    y_min = min(l['y0'] for l in linhas_validas)
    
    print(f"\nY mínimo global: {y_min:.1f}pt ({y_min/MM_TO_PT:.1f}mm)")
    
    # Filtra APENAS as linhas com Y0 muito próximo do mínimo (tolerância 2pt)
    TOLERANCIA_Y = 2  # pt - muito restrito para pegar só marcas de corte
    marcas_corte = [l for l in linhas_validas if l['y0'] <= y_min + TOLERANCIA_Y]
    
    print(f"Marcas de corte encontradas: {len(marcas_corte)}")
    for l in sorted(marcas_corte, key=lambda x: x['x']):
        print(f"  X={l['x']:.1f}pt ({l['x']/MM_TO_PT:.1f}mm) | Y0={l['y0']:.1f}pt")
    
    # Agrupa por X
    xs = [l['x'] for l in marcas_corte]
    return agrupar(xs)

def identificar_estrutura(colunas, trimbox):
    resultado = {
        'orelha_esq': None,
        'quarta_capa': None,
        'lombada': None,
        'capa': None,
        'orelha_dir': None
    }
    
    # Adiciona bordas do TrimBox
    todas = [trimbox.x0] + list(colunas) + [trimbox.x1]
    todas = sorted(set(todas))
    
    print(f"\nColunas finais: {len(todas)}")
    for i, x in enumerate(todas):
        print(f"  {i+1}: {x:.1f}pt ({x/MM_TO_PT:.1f}mm)")
    
    # Calcula intervalos
    intervalos = []
    for i in range(len(todas) - 1):
        x0, x1 = todas[i], todas[i+1]
        largura_mm = (x1 - x0) / MM_TO_PT
        # Ignora intervalos de 0 (duplicatas)
        if largura_mm > 1:  
            intervalos.append({
                'idx': i,
                'x0': x0,
                'x1': x1,
                'largura_mm': largura_mm
            })
    
    print(f"\nIntervalos:")
    for intv in intervalos:
        print(f"  {intv['idx']+1}: {intv['largura_mm']:6.1f}mm")
    
    if len(intervalos) < 1:
        print("⚠ Nenhum intervalo encontrado")
        return resultado
    
    # ESTRATÉGIA: A lombada é o MENOR intervalo próximo ao centro
    centro = (trimbox.x0 + trimbox.x1) / 2
    area_central = (trimbox.x1 - trimbox.x0) * 0.4  # 40% da largura
    
    # Filtra intervalos próximos ao centro
    intervalos_centrais = []
    for intv in intervalos:
        centro_intv = (intv['x0'] + intv['x1']) / 2
        if abs(centro_intv - centro) < area_central:
            intervalos_centrais.append(intv)
    
    if not intervalos_centrais:
        print("⚠ Nenhum intervalo na região central")
        return resultado
    
    # Ordena por largura e pega o menor
    intervalos_centrais.sort(key=lambda x: x['largura_mm'])
    lombada_intv = intervalos_centrais[0]
    
    # Encontra índice na lista original
    lombada_idx = intervalos.index(lombada_intv)
    
    print(f"\n→ LOMBADA detectada: intervalo {lombada_intv['idx']+1} ({lombada_intv['largura_mm']:.1f}mm)")
    
    # LOMBADA
    lombada_x0 = lombada_intv['x0']
    lombada_x1 = lombada_intv['x1']
    resultado['lombada'] = (lombada_x0, lombada_x1)
    
    # 4ª CAPA: intervalo antes da lombada
    if lombada_idx > 0:
        intv = intervalos[lombada_idx - 1]
        resultado['quarta_capa'] = (intv['x0'], intv['x1'])
        print(f"→ 4ª CAPA: {intv['largura_mm']:.1f}mm")
        
        # ORELHA ESQ: se há mais intervalos antes
        if lombada_idx > 1:
            resultado['orelha_esq'] = (todas[0], intv['x0'])
            print(f"→ ORELHA ESQ: {(intv['x0']-todas[0])/MM_TO_PT:.1f}mm")
    
    # CAPA: intervalo depois da lombada
    if lombada_idx < len(intervalos) - 1:
        intv = intervalos[lombada_idx + 1]
        resultado['capa'] = (intv['x0'], intv['x1'])
        print(f"→ CAPA: {intv['largura_mm']:.1f}mm")
        
        # ORELHA DIR: se há mais intervalos depois
        if lombada_idx < len(intervalos) - 2:
            resultado['orelha_dir'] = (intv['x1'], todas[-1])
            print(f"→ ORELHA DIR: {(todas[-1]-intv['x1'])/MM_TO_PT:.1f}mm")
    
    return resultado

def gerar_debug(page, estrutura, y_top, y_bottom, colunas, path_out):
    pix = page.get_pixmap(dpi=150)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).copy()
    img = img_data.reshape(pix.h, pix.w, pix.n)
    if pix.n >= 4:
        img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
    
    sx = pix.w / page.rect.width
    sy = pix.h / page.rect.height
    
    for x in colunas:
        cv2.line(img, (int(x*sx), 0), (int(x*sx), pix.h), (0, 200, 200), 2)
    
    cores = {
        'orelha_esq': (100, 100, 255),
        'quarta_capa': (255, 100, 100),
        'lombada': (0, 255, 255),
        'capa': (100, 255, 100),
        'orelha_dir': (255, 100, 255),
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
            cx = (pt1[0] + pt2[0]) // 2
            cv2.putText(img, labels.get(nome, nome), (cx - 80, pt1[1] + 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, cor, 2)
    
    cv2.imwrite(path_out, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))

def main():
    print("--- DETECTOR DE CAPA v7.0 (Y Mínimo Exato) ---")
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
    
    trimbox = page.trimbox
    y_top = trimbox.y0
    y_bottom = trimbox.y1
    print(f"TrimBox: Y={y_top:.1f} a {y_bottom:.1f}pt")
    
    # DETECÇÃO v7: Y mínimo EXATO
    colunas = detectar_marcas_corte(page)
    
    estrutura = identificar_estrutura(colunas, trimbox)
    
    print(f"\n{'='*60}")
    print("RESULTADO FINAL:")
    print('='*60)
    for nome, coords in estrutura.items():
        if coords:
            x0, x1 = coords
            print(f"  {nome:15}: {(x1-x0)/MM_TO_PT:6.1f}mm")
    
    for nome, coords in estrutura.items():
        if coords:
            x0, x1 = coords
            rect = fitz.Rect(x0, y_top, x1, y_bottom)
            page.get_pixmap(clip=rect, dpi=300).save(os.path.join(OUTPUT_DIR, f"_{nome}.png"))
            print(f"[EXPORTADO] _{nome}.png")
    
    gerar_debug(page, estrutura, y_top, y_bottom, colunas, os.path.join(OUTPUT_DIR, "DEBUG_V7.png"))
    print(f"Debug: DEBUG_V7.png")
    
    doc.close()

if __name__ == "__main__":
    main()
