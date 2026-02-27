# Packshots - Processador de Materiais Gráficos

O **Packshots** é uma ferramenta de automação para o processamento de materiais gráficos de livros. Ele facilita a criação de arquivos para divulgação, como prévias de leitura (ensaio de leitura), sumários editados por IA e extração de imagens de capa e quarta capa a partir de arquivos PDF.

## 🚀 Funcionalidades

- **Processamento de Miolo**: Gera PDFs de "ensaio de leitura" com páginas selecionadas e margens de corte aplicadas.
- **Detecção de Capas**: Identifica automaticamente marcas de corte em PDFs de capa para extrair a capa, quarta capa, lombada e orelhas.
- **Integração com IA**: Edita sumários a partir do conteúdo do livro (PDF/Epub) utilizando modelos de IA (LM Studio, OpenAI, etc).
- **Exportação Flexível**: Gera PNGs de alta qualidade para vitrines e sites de e-commerce.

## 🛠️ Módulos e Componentes

- **`main.py`**: Ponto de entrada da aplicação. Orquestra o fluxo de processamento baseado em flags.
- **`config.py`**: Centraliza todas as configurações, como diretórios de entrada/saída, palavras-chave de identificação e parâmetros de IA.
- **`modules/detector.py`**: Contém a lógica de processamento de PDFs de capa e detecção de marcas de corte.
- **`modules/miolo.py`**: Responsável pelo processamento dos arquivos de interior/miolo e integração com EPUB para IA.
- **`modules/utils.py`**: Funções utilitárias compartilhadas, como manipulação de pastas e redimensionamento de imagens.
- **`assets/prompts/`**: Armazena os prompts utilizados para a comunicação com a IA.

## ⚙️ Flags e Uso

A aplicação opera principalmente através do diretório `entrada/` e salva os resultados em `saida/`.

### Fluxo Completo (Miolo + Capa)
Processa o miolo e extrai a capa básica.
```bash
python main.py
```

### Modo Capa Detalhado
Processa apenas PDFs de capa, permitindo exportar partes específicas (lombada, orelhas, etc) conforme configurado no `config.py`.
```bash
python main.py --capa
```

## 📋 Instalação

### 1. Clonar o Repositório
```bash
git clone https://github.com/jorgelzsilva/packshots
cd packshots
```

### 2. Criar Ambiente Virtual (Virtualenv)

Crie um ambiente chamado `packshot` conforme o seu sistema operacional:

#### Windows (PowerShell/CMD)
```powershell
python -m venv packshot
.\packshot\Scripts\activate
```

#### Linux / macOS
```bash
python3 -m venv packshot
source packshot/bin/activate
```

#### WSL (Windows Subsystem for Linux)
```bash
python3 -m venv packshot
source packshot/bin/activate
```

### 3. Instalar Dependências
```bash
pip install -r requirements.txt
```

### 4. Configuração (Opcional)
Se desejar usar as funções de IA, renomeie o arquivo `.env.example` (se disponível) para `.env` e configure suas chaves de API e URLs do provedor de IA.

---
Desenvolvido por [Jorge Luiz Silva](https://github.com/jorgelzsilva).
