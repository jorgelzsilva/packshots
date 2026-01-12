"""
Módulo Detector de Capa
-----------------------
Detecta e extrai capa, quarta capa, lombada e orelhas de PDFs.
Usa marcas de corte vetoriais com filtro por Y mínimo.
"""
import os
import fitz
import cv2
import numpy as np

from config import MM_TO_PT, EXPORTAR_CAPA


def _agrupar(lista, tol=5.0):
    """Agrupa valores próximos"""
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


def _detectar_marcas_corte(page):
    """
    Detecta marcas de corte reais:
    - Linhas verticais com Y mínimo (mais próximas do topo)
    - Ignora Y negativo
    - Tolerância de 2pt
    """
    paths = page.get_drawings()
    
    linhas = []
    for p in paths:
        r = p['rect']
        w = r.width
        h = r.height
        
        if h > 8 and w < 6:
            linhas.append({
                'x': r.x0 + w/2,
                'y0': r.y0,
                'h': h
            })
    
    if not linhas:
        return []
    
    # Ignora Y negativo
    linhas_validas = [l for l in linhas if l['y0'] >= 0]
    if not linhas_validas:
        return []
    
    # Y mínimo
    y_min = min(l['y0'] for l in linhas_validas)
    
    # Filtra por Y mínimo (tolerância 2pt)
    marcas_corte = [l for l in linhas_validas if l['y0'] <= y_min + 2]
    
    # Agrupa por X
    xs = [l['x'] for l in marcas_corte]
    return _agrupar(xs)


def _identificar_estrutura(colunas, trimbox):
    """Identifica lombada, capa, quarta capa e orelhas"""
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
    
    # Calcula intervalos (ignora < 1mm)
    intervalos = []
    for i in range(len(todas) - 1):
        x0, x1 = todas[i], todas[i+1]
        largura_mm = (x1 - x0) / MM_TO_PT
        if largura_mm > 1:
            intervalos.append({
                'idx': i,
                'x0': x0,
                'x1': x1,
                'largura_mm': largura_mm
            })
    
    if len(intervalos) < 1:
        return resultado
    
    # Lombada = menor intervalo próximo ao centro
    centro = (trimbox.x0 + trimbox.x1) / 2
    area_central = (trimbox.x1 - trimbox.x0) * 0.4
    
    intervalos_centrais = [
        intv for intv in intervalos
        if abs((intv['x0'] + intv['x1']) / 2 - centro) < area_central
    ]
    
    if not intervalos_centrais:
        return resultado
    
    intervalos_centrais.sort(key=lambda x: x['largura_mm'])
    lombada_intv = intervalos_centrais[0]
    lombada_idx = intervalos.index(lombada_intv)
    
    # Lombada
    resultado['lombada'] = (lombada_intv['x0'], lombada_intv['x1'])
    
    # 4ª Capa
    if lombada_idx > 0:
        intv = intervalos[lombada_idx - 1]
        resultado['quarta_capa'] = (intv['x0'], intv['x1'])
        
        if lombada_idx > 1:
            resultado['orelha_esq'] = (todas[0], intv['x0'])
    
    # Capa
    if lombada_idx < len(intervalos) - 1:
        intv = intervalos[lombada_idx + 1]
        resultado['capa'] = (intv['x0'], intv['x1'])
        
        if lombada_idx < len(intervalos) - 2:
            resultado['orelha_dir'] = (intv['x1'], todas[-1])
    
    return resultado


def _gerar_debug(page, estrutura, y_top, y_bottom, colunas, path_out):
    """Gera imagem de debug com marcações"""
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


def processar_capa(pdf_path, output_folder, isbn, dpi=300, config_exportar=None):
    """
    Processa um PDF de capa e exporta as imagens.
    
    Args:
        pdf_path: Caminho do PDF de capa
        output_folder: Pasta de saída
        isbn: ISBN para nomear arquivos
        dpi: Resolução das imagens (padrão 300)
        config_exportar: Dict de configuração de exportação (usa EXPORTAR_CAPA se None)
    
    Returns:
        dict com caminhos dos arquivos gerados
    """
    if config_exportar is None:
        config_exportar = EXPORTAR_CAPA
    
    resultado = {
        'capa': None,
        'quarta_capa': None,
        'lombada': None,
        'orelha_esq': None,
        'orelha_dir': None,
        'estrutura': {}
    }
    
    if not os.path.exists(pdf_path):
        print(f"   [ERRO] Arquivo de capa não encontrado: {pdf_path}")
        return resultado
    
    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        
        # Obtém TrimBox para altura
        trimbox = page.trimbox
        y_top = trimbox.y0
        y_bottom = trimbox.y1
        
        # Detecta marcas de corte
        colunas = _detectar_marcas_corte(page)
        
        if not colunas:
            print(f"   [AVISO] Marcas de corte não detectadas em {pdf_path}")
            doc.close()
            return resultado
        
        # Identifica estrutura
        estrutura = _identificar_estrutura(colunas, trimbox)
        
        nomes = {
            'capa': f"{isbn}_capa.png",
            'quarta_capa': f"{isbn}_quartacapa.png",
            'lombada': f"{isbn}_lombada.png",
            'orelha_esq': f"{isbn}_orelha_esq.png",
            'orelha_dir': f"{isbn}_orelha_dir.png"
        }
        
        for parte, coords in estrutura.items():
            if coords:
                x0, x1 = coords
                largura_mm = (x1 - x0) / MM_TO_PT
                resultado['estrutura'][parte] = largura_mm
                
                # Só exporta se configurado
                if config_exportar.get(parte, False):
                    rect = fitz.Rect(x0, y_top, x1, y_bottom)
                    pix = page.get_pixmap(clip=rect, dpi=dpi)
                    
                    caminho = os.path.join(output_folder, nomes[parte])
                    pix.save(caminho)
                    resultado[parte] = caminho
                    print(f"   [EXPORTADO] {nomes[parte]} ({largura_mm:.1f}mm)")
        
        # Debug
        if config_exportar.get('debug', False):
            debug_path = os.path.join(output_folder, f"{isbn}_DEBUG.png")
            _gerar_debug(page, estrutura, y_top, y_bottom, colunas, debug_path)
            print(f"   [DEBUG] {isbn}_DEBUG.png")
        
        doc.close()
        
    except Exception as e:
        print(f"   [ERRO] Falha ao processar capa: {e}")
    
    return resultado


def processar_capa_simples(pdf_path, output_folder, isbn, dpi=300):
    """
    Extrai apenas capa e 4ª capa (para uso no fluxo principal).
    """
    config_simples = {
        'capa': True,
        'quarta_capa': True,
        'lombada': False,
        'orelha_esq': False,
        'orelha_dir': False,
        'debug': False,
    }
    return processar_capa(pdf_path, output_folder, isbn, dpi, config_simples)
