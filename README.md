# Packshot Scripts Collection

Este repositório contém um conjunto de scripts em Python para automação de geração de packshots (imagens de divulgação), detecção de marcas de corte em capas de livros (PDF) e geração de materiais promocionais (miolo, sumário via IA).

## Scripts Principais

### `detector_v7.py`
Versão mais recente do detector de marcas de corte.
- **Função:** Identifica marcas de corte (crop marks) em PDFs de capa, calculando a lombada, capa, 4ª capa e orelhas.
- **Destaque:** Usa lógica de "Y Mínimo Exato" para filtrar apenas as marcas de corte reais no topo da página.

### `script_packshot.py`
Script principal de orquestração ("Pipeline de Packshot").
- **Função:**
    - Processa capa (via `detector_capa`).
    - Processa miolo (gera PDF de "ensaio de leitura" com 15 páginas cortadas).
    - Gera PNGs de vitrine (página 1 + aleatórias).
    - Gera sumário em texto (extraindo do PDF/Epub e limpando com IA local).

### `detector_capa.py`
Módulo reutilizável para detecção de capas. Usado pelo `script_packshot.py`.

## Como Preparar o Ambiente

1. **Instale o Python 3.10+**
2. **Crie um ambiente virtual (recomendado):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```
3. **Instale as dependências:**
   ```bash
   pip install -r requirements.txt
   ```

## Como Usar

1. Crie uma pasta `entrada` na raiz do projeto.
2. Coloque os arquivos PDF (Capa e Miolo/Interior) na pasta `entrada`.
   - Exemplo:  `9788500000000.epub`, `9788500000000_capa.pdf` e `9788500000000_miolo.pdf`.
3. Execute o script desejado:
   ```bash
   python detector_v7.py
   # ou
   python script_packshot.py
   ```
4. Os resultados estarão na pasta `saida` (ou `saida_detector_v7`).

## Estrutura de Pastas

- `entrada/`: Local para colocar os arquivos PDF input.
- `saida/`: Local onde os arquivos processados (PNGs, PDFs cortados) serão salvos.
