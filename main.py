"""
Packshots - Processador de Materiais Gráficos
==============================================

Uso:
    python main.py          # Processa miolo + capa (fluxo completo)
    python main.py --capa   # Exporta apenas capas conforme config.py
"""
import os
import shutil
import argparse

from config import INPUT_DIR, OUTPUT_DIR, EXPORTAR_CAPA
from modules.miolo import processar_miolo, garantir_pasta
from modules.detector import processar_capa, processar_capa_simples


def processar_livro_completo():
    """Fluxo completo: miolo + capa básica (capa e 4ª capa)"""
    print("--- PACKSHOTS: Processamento Completo ---\n")
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
        path_capa = None
        
        for f in arquivos:
            if f.startswith(isbn) and f.endswith(".pdf"):
                f_lower = f.lower()
                if "miolo" in f_lower or "interior" in f_lower:
                    path_miolo = os.path.join(INPUT_DIR, f)
                elif "capa" in f_lower:
                    path_capa = os.path.join(INPUT_DIR, f)
        
        path_epub = os.path.join(INPUT_DIR, f"{isbn}.epub")
        
        # Processa Miolo
        if path_miolo:
            processar_miolo(path_miolo, path_epub, isbn, pasta_livro)
        else:
            print("   [ERRO] Arquivo de miolo não encontrado.")
        
        # Processa Capa (detecta e exporta capa e 4ª capa)
        if path_capa:
            print("   -> Processando capa...")
            resultado_capa = processar_capa_simples(path_capa, pasta_livro, isbn)
            
            # Copia o PDF original da capa
            nome_arquivo_capa = os.path.basename(path_capa)
            destino_capa = os.path.join(pasta_livro, nome_arquivo_capa)
            shutil.copy2(path_capa, destino_capa)
        else:
            print("   [AVISO] Arquivo de Capa não encontrado.")
    
    print("\n--- Processamento Completo Finalizado ---")


def processar_apenas_capas():
    """Modo --capa: processa apenas PDFs de capa conforme EXPORTAR_CAPA"""
    print("--- PACKSHOTS: Modo Capa ---\n")
    print("Configuração de exportação:")
    for nome, ativo in EXPORTAR_CAPA.items():
        status = "✓" if ativo else "✗"
        print(f"  {status} {nome}")
    print()
    
    garantir_pasta(OUTPUT_DIR)
    
    # Lista PDFs de capa
    arquivos = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.pdf') and 'capa' in f.lower()]
    
    if not arquivos:
        print("Nenhum PDF de capa encontrado na pasta de entrada.")
        return
    
    print(f"Encontrados {len(arquivos)} arquivo(s) de capa\n")
    
    total_exportados = 0
    for arquivo in arquivos:
        caminho = os.path.join(INPUT_DIR, arquivo)
        isbn = arquivo.split('_')[0]
        
        # Cria pasta por ISBN
        pasta_livro = os.path.join(OUTPUT_DIR, isbn)
        garantir_pasta(pasta_livro)
        
        print(f"Processando: {arquivo}")
        try:
            resultado = processar_capa(caminho, pasta_livro, isbn, config_exportar=EXPORTAR_CAPA)
            exportados = sum(1 for k, v in resultado.items() if v and k != 'estrutura')
            total_exportados += exportados
        except Exception as e:
            print(f"   [ERRO] {e}")
    
    print(f"\n--- {len(arquivos)} PDF(s) processados, {total_exportados} arquivo(s) exportados ---")


def main():
    parser = argparse.ArgumentParser(
        description="Packshots - Processador de Materiais Gráficos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python main.py          # Processa miolo + capa (fluxo completo)
  python main.py --capa   # Exporta apenas capas conforme config.py

Configure EXPORTAR_CAPA em config.py para definir quais partes exportar no modo --capa.
        """
    )
    parser.add_argument(
        '--capa',
        action='store_true',
        help='Processa apenas PDFs de capa, exportando conforme config.py'
    )
    
    args = parser.parse_args()
    
    if args.capa:
        processar_apenas_capas()
    else:
        processar_livro_completo()


if __name__ == "__main__":
    main()
