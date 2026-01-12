"""
Configurações centralizadas do Packshots
"""

# ============== DIRETÓRIOS ==============
INPUT_DIR = "./entrada"
OUTPUT_DIR = "./saida"

# ============== CONVERSÕES ==============
MM_TO_PT = 2.83465

# ============== MARGEM DE CORTE (MIOLO) ==============
MARGEM_CORTE_MM = 10.3

# ============== EXPORTAÇÃO DE CAPA ==============
# True = exportar | False = não exportar
# Usado no modo --capa
EXPORTAR_CAPA = {
    'capa': True,
    'quarta_capa': False,
    'lombada': False,
    'orelha_esq': False,
    'orelha_dir': False,
    'debug': False,
}

# ============== CONFIGURAÇÕES DE IA ==============
AI_URL = "http://localhost:1234/v1/chat/completions"
AI_MODEL = "local-model"

# Prompt para processamento de sumário
SYSTEM_PROMPT = """
Sua tarefa é receber um texto de sumário, enviado pelo usuário. O sumário poderá ou não ter tags html e você deve extrair apenas seções que sejam **partes** ou **capítulo de hierarquia principal** e passar para uma outra estrutura de tags. O Resultado final deverá ser em uma linha. Responda apenas o resultado.

**Exemplo de entrada 1:**
<p class="SUM_Cap"><span class="_Cap"><a class="TitNum_Cor" href="cap_001.xhtml">Capítulo I</a></span></p>
<p class="SUM_Cap2"><strong class="Bold_Compressed"><a class="Tit" href="cap_001.xhtml">TENDÊNCIAS PARA A FORMAÇÃO MÉDICA NO SÉCULO XXI</a></strong></p>
<p class="SUM_Autor">DANNIELLE FERNANDES GODOI, ALEXANDRE SIZILIO</p>
<p class="SUM_Cap"><span class="_Cap"><a class="TitNum_Cor" href="cap_002.xhtml">Capítulo II</a></span></p>
<p class="SUM_Cap2"><strong class="Bold_Compressed"><a class="Tit" href="cap_002.xhtml">O PAPEL DA MEDICINA DE FAMÍLIA E COMUNIDADE NA FORMAÇÃO DO MÉDICO</a></strong></p>

**Exemplo de saída 1:**
<p><b>Capítulo I</b> - TENDÊNCIAS PARA A FORMAÇÃO MÉDICA NO SÉCULO XXI<br /><b>Capítulo II</b> - O PAPEL DA MEDICINA DE FAMÍLIA E COMUNIDADE NA FORMAÇÃO DO MÉDICO</p>

**Exemplo de entrada 2:**
Introdução
1 ◼ Solidão
2 ◼ Vivendo com... o outro

**Exemplo de saída 2:**
<p><b>Capítulo 1</b> - Solidão<br /><b>Capítulo 2</b> - Vivendo com... o outro</p>

**Exemplo de entrada 3:**
Parte I Fundamentos
1 Hello, World!
1.1 Programas
Parte II Entrada e saída
9 Fluxos de entrada e saída

**Exemplo de saída 3:**
<p><b>Parte I </b> - Fundamentos<br /><b>Capítulo 1</b> - Hello, World!</p><p><b>Parte II </b> - Fundamentos<br /><b>Capítulo 9</b> - Fluxos de entrada e saída</p>

Observação: O texto de entrada pode conter números de página ou pontilhados (....). Ignore-os e foque apenas no título do capítulo e na numeração hierárquica. Se houver, inserir também apêndices e glossários, se houver capítulos antes da parte 1, também inserir. Não insira sub capítulos, como 1.1, 1.2, etc.
Lembre-se! Se houver conteúdo extra como apêndices e glossários, insira-os; O Resultado final deverá ser um html em uma linha!.
"""
