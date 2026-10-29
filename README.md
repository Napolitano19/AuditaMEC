# AuditaMEC — Validador de Documentos (Decreto nº 10.278/2020)

Aplicação desktop desenvolvida em Python, com interface dinâmica em **HTML, CSS e JavaScript** por meio do `pywebview`, destinada a apoiar a auditoria de documentos PDF relacionados aos requisitos de digitalização e preservação documental.

> **Nota:** os resultados da aplicação servem como apoio técnico à conferência documental. A avaliação final deve considerar os procedimentos institucionais e os requisitos normativos aplicáveis.

---

## 🚀 Funcionalidades

- **Motor de validação estrutural — 3 pilares (v2.3.0)**  
  Analisa características do PDF para auxiliar na distinção entre documentos nato-digitais e escaneados, considerando:
  - densidade de texto vetorial (referência indicada pelo projeto: mais de 150 caracteres);
  - presença de camada de OCR invisível após digitalização, incluindo a análise de *Render Mode 3*;
  - auditoria de metadados relacionados a software e hardware.

- **Barra de progresso dinâmica em lote (v2.4.0)**  
  Apresenta o avanço do processamento em tempo real e bloqueia os botões pertinentes durante a execução para reduzir o risco de envios duplicados.

- **Validação de DPI efetivo ajustável**  
  Analisa a resolução efetiva das imagens presentes no PDF e compara o resultado com o limite configurado, como 300 DPI.

- **Reconhecimento e classificação documental**  
  Utiliza OCR para auxiliar na identificação e classificação de documentos, como comprovantes de residência, carteiras de vacinação, históricos escolares, diplomas, CNH, quitação eleitoral e outros documentos acadêmicos e pessoais.

- **Auditoria do padrão PDF/A**  
  Verifica características relacionadas ao padrão PDF/A, voltado à preservação digital de longo prazo.

- **Auditoria de metadados e rastros de software**  
  Utiliza o ExifTool para analisar metadados e auxiliar na identificação de marcas d’água ou informações associadas a ferramentas de digitalização e edição, como CamScanner, Photoshop, Canva e Illustrator.

- **Matriz do Anexo II — partes A e B**  
  Reúne verificações de metadados associados aos requisitos do Decreto nº 10.278/2020, conforme as regras implementadas no projeto.

- **Análise de múltiplos documentos em lote**  
  Permite processar vários PDFs em uma mesma execução e consultar os resultados na interface.

- **Exportação de laudo técnico em PDF**  
  Gera um relatório consolidado com os resultados e o parecer da auditoria dos documentos analisados.

---

## 🛠️ Pré-requisitos

- **Python 3.10 ou superior**, compatível com as dependências do projeto.
- Dependências Python listadas em `requirements.txt`.
- **Tesseract OCR**, necessário para os recursos de extração e reconhecimento de texto.
- **ExifTool**, utilizado na análise de metadados.

O projeto pode utilizar os binários portáteis mantidos na raiz do repositório:

```text
Tesseract-OCR/
ExifTool/
```

Verifique também se o pacote de idioma português do Tesseract (`por.traineddata`) está disponível quando necessário.

---

## 🚀 Como executar o projeto

### 1. Clonar o repositório

```bash
git clone https://github.com/Napolitano19/VALIDADOR_DE_DPI_MEC.git
cd VALIDADOR_DE_DPI_MEC
```

### 2. Criar o ambiente virtual

```bash
python -m venv venv
```

### 3. Ativar o ambiente virtual no Windows

```powershell
.\venv\Scripts\activate
```

### 4. Instalar as dependências

```bash
pip install -r requirements.txt
```

### 5. Executar a aplicação

```bash
python AuditaMEC.py
```

---

## 📦 Gerando o executável (.exe)

Para gerar um executável único com o PyInstaller, incluindo a interface HTML e as pastas locais do ExifTool e do Tesseract OCR, execute no PowerShell, a partir da raiz do projeto:

```powershell
pyinstaller --noconsole --onefile `
  --add-data "index.html;." `
  --add-data "ExifTool;ExifTool" `
  --add-data "Tesseract-OCR;Tesseract-OCR" `
  AuditaMEC.py
```

O executável deverá ser gerado em:

```text
dist/AuditaMEC.exe
```

> **Importante:** este comando documenta a configuração informada para o projeto. Confirme que os caminhos e a forma como o código localiza os binários funcionam corretamente no executável empacotado antes de distribuir a versão.

---

## 📁 Estrutura do projeto

Estrutura esperada, considerando os arquivos e diretórios descritos:

```text
VALIDADOR_DE_DPI_MEC/
├── ExifTool/
│   └── exiftool.exe
├── Tesseract-OCR/
├── index.html
├── AuditaMEC.py
├── requirements.txt
└── README.md
```

Outros arquivos auxiliares de testes ou configuração podem existir no repositório e devem ser mantidos conforme utilizados pelo projeto.

---

## 🔎 Fluxo geral de auditoria

```text
Documento PDF
    │
    ▼
Leitura e análise do PDF
    │
    ├──► Origem e estrutura do documento
    │       ├── Texto/vetores nativos
    │       ├── Conteúdo escaneado
    │       └── Análise de OCR invisível
    │
    ├──► Análise de imagens e DPI efetivo
    ├──► Extração/reconhecimento de texto (OCR)
    ├──► Auditoria de metadados (ExifTool)
    ├──► Verificações relacionadas a PDF/A
    └──► Aplicação das regras de auditoria
                │
                ▼
        Resultado da auditoria
                │
                ▼
        Laudo técnico em PDF
```

---

## ⚙️ Tecnologias utilizadas

- Python
- PyMuPDF (`fitz`)
- PyWebView
- HTML5, CSS3 e JavaScript
- Tesseract OCR
- ExifTool
- ReportLab
- PyInstaller

---

## 📚 Referência normativa

O projeto tem como referência o **Decreto Federal nº 10.278/2020**, relacionado aos requisitos técnicos para digitalização de documentos e à produção de efeitos legais equivalentes aos dos documentos originais, conforme aplicável.

A ferramenta auxilia na análise técnica dos arquivos, mas seus resultados não substituem a avaliação dos responsáveis nem a verificação dos requisitos normativos e institucionais aplicáveis a cada caso.

---

## 📌 Repositório

**GitHub:** [Napolitano19/VALIDADOR_DE_DPI_MEC](https://github.com/Napolitano19/VALIDADOR_DE_DPI_MEC)
