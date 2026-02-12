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

from config import INPUT_DIR, OUTPUT_DIR, EXPORTAR_CAPA, KEYWORDS_MIOLO, KEYWORDS_CAPA
from modules.utils import garantir_pasta
from modules.miolo import processar_miolo
from modules.detector import processar_capa, processar_capa_simples


def extrair_identificador(nome_arquivo):
    """
    Extrai um identificador único do nome do arquivo.
    Tenta pegar o ISBN (primeira parte antes de '_') ou usa o nome do arquivo sem extensão.
    """
    nome_sem_ext = os.path.splitext(nome_arquivo)[0]
    if '_' in nome_sem_ext:
        partes = nome_sem_ext.split('_')
        # Se a primeira parte parece ser um prefixo genérico como "Capa", tenta ser mais específico
        if partes[0].lower() in KEYWORDS_CAPA and len(partes) > 1:
            return f"{partes[0]}_{partes[1]}"
        return partes[0]
    return nome_sem_ext


def processar_livro_completo():
    """Fluxo completo: miolo + capa básica (capa e 4ª capa)"""
    print("--- PACKSHOTS: Processamento Completo ---\n")
    garantir_pasta(OUTPUT_DIR)
    
    arquivos = os.listdir(INPUT_DIR)
    
    # Identifica livros pelo miolo
    identificadores = set()
    for f in arquivos:
        f_lower = f.lower()
        if f_lower.endswith('.pdf') and any(kw in f_lower for kw in KEYWORDS_MIOLO):
            identificadores.add(extrair_identificador(f))
    
    if not identificadores:
        print("Nenhum arquivo de Miolo identificado.")
        return
    
    for ident in identificadores:
        print(f"\nIDENTIFICADOR: {ident}")
        pasta_livro = os.path.join(OUTPUT_DIR, ident)
        garantir_pasta(pasta_livro)
        
        # Localiza arquivos relacionados ao identificador
        path_miolo = None
        path_capa = None
        
        for f in arquivos:
            if not f.lower().endswith('.pdf'):
                continue
            
            # Se o arquivo começa com o identificador
            if f.startswith(ident):
                f_lower = f.lower()
                if any(kw in f_lower for kw in KEYWORDS_MIOLO):
                    path_miolo = os.path.join(INPUT_DIR, f)
                elif any(kw in f_lower for kw in KEYWORDS_CAPA):
                    path_capa = os.path.join(INPUT_DIR, f)
        
        # Tenta achar um EPUB correspondente
        path_epub = os.path.join(INPUT_DIR, f"{ident}.epub")
        if not os.path.exists(path_epub):
            # Tenta busca mais flexível se necessário
            pass
        
        # Processa Miolo
        if path_miolo:
            processar_miolo(path_miolo, path_epub if os.path.exists(path_epub) else None, ident, pasta_livro)
        else:
            print(f"   [AVISO] Arquivo de miolo para '{ident}' não encontrado.")
        
        # Processa Capa Simples
        if path_capa:
            print("   -> Processando capa...")
            processar_capa_simples(path_capa, pasta_livro, ident)
            
            # Copia o PDF original da capa
            destino_capa = os.path.join(pasta_livro, os.path.basename(path_capa))
            shutil.copy2(path_capa, destino_capa)
    
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
    arquivos = [
        f for f in os.listdir(INPUT_DIR) 
        if f.lower().endswith('.pdf') and any(kw in f.lower() for kw in KEYWORDS_CAPA)
    ]
    
    if not arquivos:
        print("Nenhum PDF de capa encontrado na pasta de entrada.")
        return
    
    print(f"Encontrados {len(arquivos)} arquivo(s) de capa\n")
    
    total_exportados = 0
    for arquivo in arquivos:
        caminho = os.path.join(INPUT_DIR, arquivo)
        ident = extrair_identificador(arquivo)
        
        # Cria pasta por Identificador para evitar colisões
        pasta_livro = os.path.join(OUTPUT_DIR, ident)
        garantir_pasta(pasta_livro)
        
        print(f"Processando: {arquivo} (Pasta: {ident})")
        try:
            resultado = processar_capa(caminho, pasta_livro, ident, config_exportar=EXPORTAR_CAPA)
            exportados = sum(1 for k, v in resultado.items() if v and k != 'estrutura')
            total_exportados += exportados
        except Exception as e:
            print(f"   [ERRO] Falha ao processar '{arquivo}': {e}")
    
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
    
    # Design by Contract: Garantir diretório de entrada
    assert os.path.isdir(INPUT_DIR), f"Diretório de entrada não encontrado: {INPUT_DIR}"
    
    if args.capa:
        processar_apenas_capas()
    else:
        processar_livro_completo()


if __name__ == "__main__":
    main()
