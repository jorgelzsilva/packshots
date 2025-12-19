"""
Analisador detalhado de marcas - mostra TODAS as linhas verticais
"""
import os
import fitz

INPUT_DIR = "./entrada"
MM_TO_PT = 2.83465

def main():
    arquivo = next((f for f in os.listdir(INPUT_DIR) if f.endswith('.pdf')), None)
    if not arquivo: return
    
    doc = fitz.open(os.path.join(INPUT_DIR, arquivo))
    page = doc[0]
    
    # Redireciona para arquivo
    import sys
    with open("marcas_detalhadas.txt", "w", encoding="utf-8") as f:
        sys.stdout = f
        analisar_marcas(page)
        sys.stdout = sys.__stdout__
    doc.close()
    print("Salvo em: marcas_detalhadas.txt")

def analisar_marcas(page):
    
    paths = page.get_drawings()
    
    # Coleta TODAS as linhas verticais
    linhas = []
    for p in paths:
        r = p['rect']
        w = r.width
        h = r.height
        
        if h > 8 and w < 6:
            linhas.append({
                'x': r.x0 + w/2,
                'y0': r.y0,
                'y1': r.y1,
                'h': h,
                'cor': p.get('color')
            })
    
    # Ordena por X
    linhas.sort(key=lambda l: l['x'])
    
    print(f"Total linhas verticais: {len(linhas)}")
    print(f"\n{'X (mm)':>10} | {'Y0 (mm)':>10} | {'Y1 (mm)':>10} | {'Altura':>8} | Cor")
    print("-" * 70)
    
    for l in linhas:
        x_mm = l['x'] / MM_TO_PT
        y0_mm = l['y0'] / MM_TO_PT
        y1_mm = l['y1'] / MM_TO_PT
        h_mm = l['h'] / MM_TO_PT
        
        # Destaca se está na região de interesse (entre 479mm e 490mm que é onde deveria estar o fim da capa)
        destaque = ""
        if 470 < x_mm < 490:
            destaque = " <-- REGIÃO CAPA"
        
        print(f"{x_mm:>10.1f} | {y0_mm:>10.1f} | {y1_mm:>10.1f} | {h_mm:>8.1f} | {l['cor']}{destaque}")

if __name__ == "__main__":
    main()
