"""
Módulo de Verificação de Anotações
----------------------------------
Detecta comentários/anotações em PDFs antes do processamento,
para que o usuário possa revisar arquivos possivelmente não finalizados.
"""
import os
import fitz

# Limite de caracteres do texto da anotação exibido na UI
MAX_TEXTO_ANOTACAO = 300


def listar_anotacoes(pdf_path: str) -> list:
    """
    Lista todas as anotações (comentários, destaques, etc.) de um PDF.

    Hyperlinks não contam: ficam em page.links(), não em page.annots().

    Returns:
        Lista de dicts: {'pagina': int, 'tipo': str, 'autor': str, 'texto': str}
    """
    assert os.path.exists(pdf_path), f"Arquivo não encontrado: {pdf_path}"

    anotacoes = []
    doc = fitz.open(pdf_path)
    try:
        for num_pagina, page in enumerate(doc, start=1):
            for annot in page.annots() or []:
                info = annot.info or {}
                anotacoes.append({
                    'pagina': num_pagina,
                    'tipo': annot.type[1] if len(annot.type) > 1 else str(annot.type),
                    'autor': info.get('title', ''),
                    'texto': (info.get('content') or '')[:MAX_TEXTO_ANOTACAO],
                })
    finally:
        doc.close()
    return anotacoes
