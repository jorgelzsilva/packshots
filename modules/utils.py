"""
Módulo de Utilitários Compartilhados
------------------------------------
Contém funções comuns usadas por múltiplos módulos do projeto.
Seguindo o princípio DRY (Don't Repeat Yourself).
"""
import os
import io
from PIL import Image

from config import KEYWORDS_CAPA


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


def garantir_pasta(pasta: str):
    """
    Cria a pasta se ela não existir.
    
    Precondição: pasta deve ser uma string não vazia.
    """
    assert pasta and isinstance(pasta, str), "O caminho da pasta deve ser uma string válida."
    if not os.path.exists(pasta):
        os.makedirs(pasta)


def salvar_png_redimensionado(pix, caminho: str, largura_alvo: int = None):
    """
    Salva um pixmap do PyMuPDF como PNG com redimensionamento opcional.
    
    Args:
        pix: O pixmap do PyMuPDF.
        caminho: Caminho de destino para o PNG.
        largura_alvo: Largura desejada em pixels. Se None ou <= 0, mantém original.
    """
    assert caminho and isinstance(caminho, str), "O caminho de destino deve ser uma string válida."
    
    if largura_alvo and largura_alvo > 0:
        # Converte pixmap para PIL Image
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))
        
        # Calcula nova altura mantendo proporção
        largura_original, altura_original = img.size
        proporcao = altura_original / largura_original
        nova_altura = int(largura_alvo * proporcao)
        
        # Redimensiona e salva
        # Usando Resampling.LANCZOS se disponível (Pillow >= 10.0.0 uses Resampling)
        # Pillow fallback for older versions if needed, but here we assume modern environment
        try:
            resample_filter = Image.Resampling.LANCZOS
        except AttributeError:
            resample_filter = Image.LANCZOS
            
        img_redimensionada = img.resize((largura_alvo, nova_altura), resample_filter)
        img_redimensionada.save(caminho)
    else:
        pix.save(caminho)
