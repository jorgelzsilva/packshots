import fitz  # PyMuPDF
import os

# --- CONFIG ---
INPUT_DIR = "./entrada"

def analisar_pdf_profundo():
    print("--- INICIANDO RAIO-X DO PDF ---")
    
    # Pega o primeiro PDF de capa
    arquivos = os.listdir(INPUT_DIR)
    arquivo_capa = next((f for f in arquivos if f.endswith('.pdf') and 'capa' in f.lower()), None)
    
    if not arquivo_capa:
        print("ERRO: Nenhuma capa encontrada.")
        return

    path = os.path.join(INPUT_DIR, arquivo_capa)
    print(f"Analisando arquivo: {arquivo_capa}")
    
    doc = fitz.open(path)
    page = doc[0]
    
    # 1. GEOMETRIA BÁSICA
    print(f"\n[1] GEOMETRIA DA PÁGINA")
    print(f"    MediaBox (Papel Total): {page.mediabox}")
    print(f"    CropBox (Área Visível): {page.cropbox}")
    print(f"    Rotação: {page.rotation}")
    
    # 2. IMAGENS RASTER (BITMAPS)
    # Se houver muitas imagens, pode ser que a marca de corte seja uma delas
    imgs = page.get_images(full=True)
    print(f"\n[2] IMAGENS RASTERIZADAS (BITMAPS)")
    print(f"    Total de imagens encontradas: {len(imgs)}")
    for i, img in enumerate(imgs):
        xref = img[0]
        base_img = doc.extract_image(xref)
        info = f"Ext: {base_img['ext']}, Size: {base_img['width']}x{base_img['height']}, Colorspace: {base_img['colorspace']}"
        print(f"    Imagem {i+1}: {info}")
        # Localiza onde a imagem está na página
        rects = page.get_image_rects(xref)
        for r in rects:
            print(f"       -> Posicionada em: {r}")

    # 3. VETORES (DRAWINGS)
    # Aqui vamos listar os tipos de traços e preenchimentos
    paths = page.get_drawings()
    print(f"\n[3] VETORES E DESENHOS")
    print(f"    Total de caminhos (paths) encontrados: {len(paths)}")
    
    cores_encontradas = {} # Para agrupar estatísticas
    linhas_corte_candidatas = []
    
    for p in paths:
        # Extrai dados
        rect = p['rect']
        fill = p.get('fill')
        stroke = p.get('stroke')
        width = rect.width
        height = rect.height
        
        # Identificador de cor para o relatório
        cor_desc = "Sem Cor"
        if stroke: cor_desc = f"Stroke {stroke}"
        if fill: cor_desc = f"Fill {fill}"
        
        # Conta ocorrências dessa cor
        cores_encontradas[cor_desc] = cores_encontradas.get(cor_desc, 0) + 1
        
        # LÓGICA DE DETETIVE: É um candidato a marca de corte?
        # Critério: Objeto fino (<5pt) e alto (>10pt) OU largo (>10pt) e baixo (<5pt)
        # E com cor "forte" (soma dos canais alta ou preto total)
        eh_fino = (width < 5 and height > 10) or (height < 5 and width > 10)
        
        # Verifica intensidade da cor (busca por preto/registro)
        tem_tinta = False
        vals = stroke if stroke else fill
        if vals:
            # Se for CMYK (4 canais) e soma > 3.0 (ex: 1,1,1,1 ou 0.8,0.8,0.8,1)
            if len(vals) == 4 and sum(vals) > 3.0: tem_tinta = True
            # Se for RGB (3 canais) e soma < 0.2 (Preto)
            elif len(vals) == 3 and sum(vals) < 0.2: tem_tinta = True
            # Se for Gray (1 canal) e valor < 0.2
            elif len(vals) == 1 and vals[0] < 0.2: tem_tinta = True
            
        if eh_fino and tem_tinta:
            linhas_corte_candidatas.append(f"RECT: {rect} | COR: {cor_desc}")

    # 4. RELATÓRIO DE CORES
    print(f"\n[4] RESUMO DE CORES NOS VETORES (Top 10)")
    sorted_cores = sorted(cores_encontradas.items(), key=lambda item: item[1], reverse=True)
    for cor, qtd in sorted_cores[:10]:
        print(f"    {qtd} objetos com: {cor}")

    # 5. CANDIDATOS A LINHAS DE CORTE
    print(f"\n[5] OBJETOS SUSPEITOS DE SEREM MARCAS DE CORTE")
    if linhas_corte_candidatas:
        print(f"    Encontrados {len(linhas_corte_candidatas)} candidatos:")
        for c in linhas_corte_candidatas[:20]: # Mostra só os primeiros 20
            print(f"    -> {c}")
    else:
        print("    Nenhum objeto com formato de 'linha fina' e 'cor escura' foi encontrado.")

    print("\n--- FIM DA ANÁLISE ---")

if __name__ == "__main__":
    analisar_pdf_profundo()