"""
Detector de Capa - Módulo
-------------------------
Detecta e extrai capa, quarta capa, lombada e orelhas de PDFs de capa.
Usa marcas de corte vetoriais com filtro por Y mínimo.

Uso:
    from detector_capa import processar_capa
    
    resultado = processar_capa(caminho_pdf, pasta_saida, isbn)
    # resultado['capa'] -> caminho do PNG da capa
    # resultado['quarta_capa'] -> caminho do PNG da 4ª capa
"""
import os
import fitz
import cv2
import numpy as np

MM_TO_PT = 2.83465

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

def processar_capa(pdf_path, output_folder, isbn, dpi=300, apenas_capa_quarta=True):
    """
    Processa um PDF de capa e exporta as imagens.
    
    Args:
        pdf_path: Caminho do PDF de capa
        output_folder: Pasta de saída
        isbn: ISBN para nomear arquivos
        dpi: Resolução das imagens (padrão 300)
        apenas_capa_quarta: Se True, exporta apenas capa e 4ª capa (padrão)
                           Se False, exporta todos (lombada, orelhas também)
    
    Returns:
        dict com caminhos dos arquivos gerados:
        - 'capa': caminho do PNG da capa
        - 'quarta_capa': caminho do PNG da 4ª capa
        - 'lombada': caminho do PNG da lombada (se apenas_capa_quarta=False)
        - 'orelha_esq': caminho do PNG da orelha esquerda (se apenas_capa_quarta=False)
        - 'orelha_dir': caminho do PNG da orelha direita (se apenas_capa_quarta=False)
        - 'estrutura': dict com as medidas em mm
    """
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
        
        # Define quais partes exportar
        if apenas_capa_quarta:
            partes_exportar = ['capa', 'quarta_capa']
        else:
            partes_exportar = ['capa', 'quarta_capa', 'lombada', 'orelha_esq', 'orelha_dir']
        
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
                
                # Só exporta se estiver na lista
                if parte in partes_exportar:
                    rect = fitz.Rect(x0, y_top, x1, y_bottom)
                    pix = page.get_pixmap(clip=rect, dpi=dpi)
                    
                    caminho = os.path.join(output_folder, nomes[parte])
                    pix.save(caminho)
                    resultado[parte] = caminho
        
        doc.close()
        
        # Log apenas para itens exportados
        if resultado['capa']:
            print(f"   [OK] Capa exportada ({resultado['estrutura'].get('capa', 0):.1f}mm)")
        if resultado['quarta_capa']:
            print(f"   [OK] 4ª Capa exportada ({resultado['estrutura'].get('quarta_capa', 0):.1f}mm)")
        if not apenas_capa_quarta:
            if resultado['lombada']:
                print(f"   [OK] Lombada exportada ({resultado['estrutura'].get('lombada', 0):.1f}mm)")
        
    except Exception as e:
        print(f"   [ERRO] Falha ao processar capa: {e}")
    
    return resultado

# Função de conveniência para uso direto
def extrair_capa_e_quarta(pdf_path, output_folder, isbn, dpi=300):
    """
    Extrai apenas capa e 4ª capa de um PDF.
    
    Returns:
        tuple: (caminho_capa, caminho_quarta_capa) ou (None, None) se falhar
    """
    resultado = processar_capa(pdf_path, output_folder, isbn, dpi)
    return resultado.get('capa'), resultado.get('quarta_capa')
