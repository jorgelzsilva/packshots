import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

# ============== DIRETÓRIOS ==============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "entrada")
OUTPUT_DIR = os.path.join(BASE_DIR, "saida")
WEBJOBS_DIR = os.path.join(BASE_DIR, "webjobs")

# ============== CONVERSÕES ==============
MM_TO_PT = 2.83465

# ============== MARGEM DE CORTE (MIOLO) ==============
MARGEM_CORTE_MM = 10.3

# ============== IDENTIFICAÇÃO DE ARQUIVOS ==============
# Palavras-chave para identificar tipos de arquivos nos nomes
KEYWORDS_MIOLO = ['miolo', 'interior']
KEYWORDS_CAPA = ['capa']

# ============== LARGURA DE EXPORTAÇÃO PNG ==============
# Largura em pixels para exportação de PNGs
EXPORT_PNG_WIDTH = 1400  # Ex: 1400, 800, ou None para manter original

# ============== EXPORTAÇÃO DE CAPA ==============
# True = exportar | False = não exportar
# Usado no modo --capa
EXPORTAR_CAPA = {
    'capa': True,
    'quarta_capa': True,
    'lombada': False,
    'orelha_esq': False,
    'orelha_dir': False,
    'debug': False,
}

# ============== CONFIGURAÇÕES DE IA ==============
AI_PROVIDER = os.getenv("AI_PROVIDER", "lm-studio")
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:1234/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "lm-studio")
AI_MODEL = os.getenv("AI_MODEL", "local-model")

# Adiciona /chat/completions se não estiver na URL
AI_URL = AI_BASE_URL
if not AI_URL.endswith("/chat/completions"):
    AI_URL = AI_URL.rstrip("/") + "/chat/completions"

# Carrega o Prompt de IA de arquivo externo
PROMPT_PATH = os.path.join(BASE_DIR, "assets", "prompts", "sumario_ia.txt")
SYSTEM_PROMPT = ""
if os.path.exists(PROMPT_PATH):
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read().strip()
else:
    SYSTEM_PROMPT = "Extraia o sumário do texto fornecido."
