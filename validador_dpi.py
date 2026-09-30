import os
import sys
import json
import datetime
import re
import hashlib
import fitz  # PyMuPDF
import pytesseract
import subprocess
from PIL import Image, ImageStat
import webview
import numpy as np

# ReportLab para geração de laudos em PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# ==============================================================================
# CONFIGURAÇÃO DE CAMINHOS LOCAIS E PORTÁTEIS
# ==============================================================================
def obter_caminho_base():
    """Retorna o caminho base do projeto, suportando execução direta e PyInstaller."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = obter_caminho_base()

# Configuração do Tesseract OCR
TESSERACT_LOCAL = os.path.join(BASE_DIR, "Tesseract-OCR", "tesseract.exe")
if os.path.exists(TESSERACT_LOCAL):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_LOCAL
else:
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Configuração do ExifTool
EXIFTOOL_LOCAL = os.path.join(BASE_DIR, "ExifTool", "exiftool.exe")
if not os.path.exists(EXIFTOOL_LOCAL):
    EXIFTOOL_LOCAL = "exiftool"


# ==============================================================================
# FUNÇÕES AUXILIARES DE ANÁLISE E CRIPTOGRAFIA
# ==============================================================================
def limpar_string_metadado(val):
    """Sanitiza strings de metadados removendo caracteres binários/corrompidos."""
    if not val or val == "N/A":
        return "N/A"
    s = str(val).strip()
    s_limpa = re.sub(r'[^\x20-\x7E]', '', s).strip()
    return s_limpa if len(s_limpa) >= 2 else "N/A"


def calcular_sha256(caminho_arquivo):
    """Gera a hash SHA-256 do arquivo digital para garantia de integridade (Anexo II - Decreto 10.278/2020)."""
    try:
        sha256 = hashlib.sha256()
        with open(caminho_arquivo, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except Exception as e:
        print(f"Erro ao calcular SHA-256: {e}")
        return "N/A"

def analisar_modo_cor_real(pixmap):
    """
    Analisa a imagem extraída do PDF usando matrizes NumPy.
    Determina: 'Monocromático', 'Escala de Cinza' ou 'Colorido'.
    """
    try:
        if pixmap.colorspace and pixmap.colorspace.n == 1:
            return "Escala de Cinza"

        img_pil = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
        img_thumb = img_pil.resize((500, 500))
        img_np = np.array(img_thumb, dtype=np.int16)
        
        variacao_cor = np.ptp(img_np, axis=2)
        pixels_coloridos = np.sum(variacao_cor > 28)

        if pixels_coloridos >= 30:
            return "Colorido"

        stat_gray = ImageStat.Stat(img_thumb.convert('L'))
        if stat_gray.stddev[0] > 105:
            return "Monocromático"
        
        return "Escala de Cinza"

    except Exception as e:
        print(f"Erro na análise do modo de cor: {e}")
        return "Colorido"

# ==============================================================================
# FUNÇÃO PARA AUDITAR OS METADADOS (ANEXO II - PARTE A)
# ==============================================================================
def auditar_metadados_com_metodologia(caminho_pdf):
    """
    Audita estritamente os 8 metadados do Anexo II (Parte A) do Decreto 10.278/2020.
    Retorna apenas o que estiver fisicamente presente no PDF e calcula o Hash SHA-256.
    """
    doc = fitz.open(caminho_pdf)
    meta = doc.metadata or {}
    doc.close()

    # 1. Assunto (Nativo: keywords ou subject)
    assunto_nativo = meta.get('keywords') or meta.get('subject')
    val_assunto = assunto_nativo.strip() if assunto_nativo and assunto_nativo.strip() else "Ausente"
    parecer_assunto = "✅ CONFORME" if val_assunto != "Ausente" else "⚠️ AVISO: Não localizado nas propriedades nativas do PDF."

    # 2. Autor (nome) (Nativo: author)
    autor_nativo = meta.get('author', '').strip()
    if not autor_nativo:
        val_autor = "Ausente"
        parecer_autor = "⚠️ AVISO: Propriedade 'author' ausente no PDF."
    else:
        val_autor = autor_nativo
        genericos = ['admin', 'administrator', 'user', 'usuario', 'kawan', 'print', 'microsoft']
        if any(g in autor_nativo.lower() for g in genericos):
            parecer_autor = f"⚠️ AVISO: Presente ({autor_nativo}), mas refere-se a conta/usuário local de sistema e não à IES emissora."
        else:
            parecer_autor = "✅ CONFORME"

    # 3. Data e local da digitalização
    data_bruta = meta.get('creationDate') or meta.get('modDate')
    data_formatada = "Ausente"
    if data_bruta:
        clean_str = re.sub(r'^[DF]:', '', str(data_bruta))
        match = re.match(r'(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})', clean_str)
        if match:
            ano, mes, dia, hora, minuto, segundo = match.groups()
            data_formatada = f"{dia}/{mes}/{ano} {hora}:{minuto}:{segundo}"
        else:
            data_formatada = str(data_bruta)

    val_data_local = f"Data/Hora: {data_formatada} | Local: Ausente"
    parecer_data_local = "⚠️ AVISO: Data extraída do cabeçalho. O container do PDF não armazena geolocalização/local."

    # 4. Identificador do documento digital
    val_id = "Ausente"
    parecer_id = "ℹ️ INFO: Identificador único de responsabilidade do sistema de acervo (Unimestre) no ato do arquivamento."

    # 5. Responsável pela digitalização
    val_resp = "Ausente"
    parecer_resp = "⚠️ AVISO: Responsável legal/operador não registrado no PDF. Requer identificação no envio ao Unimestre."

    # 6. Título
    titulo_nativo = meta.get('title', '').strip()
    if titulo_nativo:
        val_titulo = titulo_nativo
        parecer_titulo = "✅ CONFORME"
    else:
        nome_arquivo = os.path.basename(caminho_pdf)
        val_titulo = f"{nome_arquivo} (Título Atribuído)"
        parecer_titulo = "⚠️ AVISO: Propriedade 'title' nativa ausente. Utilizado o nome do arquivo."

    # 7. Tipo documental
    val_tipo = "Ausente"
    parecer_tipo = "⚠️️ AVISO: Tipo documental não gravado na estrutura do PDF. Requer atribuição via taxonomia no Unimestre."

    # 8. Hash (checksum) da imagem
    val_hash = calcular_sha256(caminho_pdf)
    parecer_hash = "✅ CONFORME: Algoritmo SHA-256 calculated sobre os bytes brutos do arquivo."

    return [
        {"campo": "Assunto", "valor": val_assunto, "parecer": parecer_assunto},
        {"campo": "Autor (nome)", "valor": val_autor, "parecer": parecer_autor},
        {"campo": "Data e local da digitalização", "valor": val_data_local, "parecer": parecer_data_local},
        {"campo": "Identificador do documento digital", "valor": val_id, "parecer": parecer_id},
        {"campo": "Responsável pela digitalização", "valor": val_resp, "parecer": parecer_resp},
        {"campo": "Título", "valor": val_titulo, "parecer": parecer_titulo},
        {"campo": "Tipo documental", "valor": val_tipo, "parecer": parecer_tipo},
        {"campo": "Hash (checksum) da imagem", "valor": val_hash, "parecer": parecer_hash},
    ]

# ==============================================================================
# CLASSE DE LÓGICA DA APLICAÇÃO (API PYWEBVIEW)
# ==============================================================================
class ApiValidador:
    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def selecionar_arquivos(self):
        """Abre o diálogo de seleção de ficheiros PDF."""
        try:
            file_type = webview.FileDialog.OPEN if hasattr(webview, 'FileDialog') else webview.OPEN_DIALOG
            ficheiros = self._window.create_file_dialog(
                file_type, 
                allow_multiple=True, 
                file_types=('Arquivos PDF (*.pdf)',)
            )
            return list(ficheiros) if ficheiros else []
        except Exception as e:
            print(f"Erro ao abrir janela de arquivos: {str(e)}")
            return []

    def _extrair_metadados_exiftool(self, caminho_pdf):
        """Extrai metadados completos do PDF utilizando o ExifTool."""
        try:
            cmd = [EXIFTOOL_LOCAL, "-j", caminho_pdf]
            resultado = subprocess.run(cmd, capture_output=True, text=True, check=True)
            dados = json.loads(resultado.stdout)
            if dados and isinstance(dados, list):
                return dados[0]
        except Exception as e:
            print(f"Erro ao ler metadados com ExifTool: {str(e)}")
        return {}

    def analisar_documentos(self, caminhos, auditar_softwares=False, exigir_pdfa=False, dpi_minimo=300):
        """Executa a verificação técnica completa em cada ficheiro PDF fornecido."""
        resultados = []
        softwares_suspeitos = ["PHOTOSHOP", "CANVA", "ILLUSTRATOR", "CORELDRAW", "GIMP", "INKSCAPE"]

        for caminho in caminhos:
            nome_arquivo = os.path.basename(caminho)
            erros = []
            hash_sha256 = calcular_sha256(caminho)
            
            try:
                doc = fitz.open(caminho)
                total_paginas = len(doc)
                
                eh_nato_digital = False
                dpi_minimo_encontrado = 9999
                modo_cor_final = "Monocromático"
                tipo_documento = "Geral / Desconhecido"
                texto_completo_ocr = ""

                # 1. Análise das páginas
                for num_pag in range(total_paginas):
                    pagina = doc[num_pag]
                    rotacao = pagina.rotation
                    
                    if rotacao != 0:
                        erros.append(f"Página {num_pag + 1} está rotacionada ({rotacao}°). Fundamento Legal: Anexo I do Decreto nº 10.278/2020.")

                    texto_pagina = pagina.get_text()
                    if texto_pagina and len(texto_pagina.strip()) > 50:
                        eh_nato_digital = True
                        texto_completo_ocr += f" {texto_pagina}"

                    lista_imagens = pagina.get_images()
                    
                    if not lista_imagens and not eh_nato_digital:
                        erros.append(f"Página {num_pag + 1} não contém imagem nem texto legível.")
                        continue

                    for img in lista_imagens:
                        xref = img[0]
                        pix = fitz.Pixmap(doc, xref)
                        
                        dpi_x = round((pix.width / pagina.rect.width) * 72) if pagina.rect.width > 0 else 0
                        dpi_y = round((pix.height / pagina.rect.height) * 72) if pagina.rect.height > 0 else 0
                        dpi_efetivo = min(dpi_x, dpi_y)

                        if dpi_efetivo < dpi_minimo_encontrado and dpi_efetivo > 0:
                            dpi_minimo_encontrado = dpi_efetivo

                        cor_img = analisar_modo_cor_real(pix)
                        if cor_img == "Colorido":
                            modo_cor_final = "Colorido"
                        elif cor_img == "Escala de Cinza" and modo_cor_final != "Colorido":
                            modo_cor_final = "Escala de Cinza"

                        if not eh_nato_digital and len(texto_pagina.strip()) <= 50:
                            try:
                                img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                                texto_ocr = pytesseract.image_to_string(img_pil, lang='por+eng')
                                texto_completo_ocr += f" {texto_ocr}"
                            except Exception as err_ocr:
                                print(f"Aviso no OCR da pág {num_pag + 1}: {str(err_ocr)}")

                # 2. Resolução DPI
                dpi_final_str = "Nativo (Vetor)" if eh_nato_digital else str(dpi_minimo_encontrado if dpi_minimo_encontrado != 9999 else "N/A")
                
                if not eh_nato_digital and dpi_minimo_encontrado < dpi_minimo:
                    erros.append(f"Resolução insuficiente ({dpi_minimo_encontrado} DPI encontrado vs {dpi_minimo} DPI exigido). Fundamento Legal: Anexo I do Decreto nº 10.278/2020.")

                # 3. Classificação por tipo documental
                txt_lower = texto_completo_ocr.lower()
                if "vacina" in txt_lower or "rubéola" in txt_lower or "imunização" in txt_lower:
                    tipo_documento = "Comprovante / Carteira de Vacinação de Rubéola"
                elif "historico escolar" in txt_lower or "histórico escolar" in txt_lower:
                    tipo_documento = "Histórico Escolar"
                elif "diploma" in txt_lower or "certificado" in txt_lower:
                    tipo_documento = "Certificado / Diploma"
                elif "quitação eleitoral" in txt_lower or "quitacao eleitoral" in txt_lower:
                    tipo_documento = "Quitação Eleitoral"
                elif "carteira nacional de habilitação" in txt_lower or "cnh" in txt_lower or "identidade" in txt_lower:
                    tipo_documento = "Carteira de Identidade / CNH"
                elif "militar" in txt_lower or "reservista" in txt_lower:
                    tipo_documento = "Comprovante Militar"

                # 4. Metadados e verificação de PDF/A
                metadados_exif = self._extrair_metadados_exiftool(caminho)
                
                eh_pdfa = False
                if "pdfa" in str(metadados_exif.get("GTS_PDFAConformance", "")).lower() or \
                   "pdfa" in str(metadados_exif.get("PDFVersion", "")).lower() or \
                   metadados_exif.get("pdfaid:part") is not None:
                    eh_pdfa = True

                if exigir_pdfa and not eh_pdfa:
                    erros.append("O ficheiro não está no formato preservado PDF/A. Fundamento Legal: Decreto nº 10.278/2020.")

                autor = str(metadados_exif.get("Author", "")).upper()
                criador = str(metadados_exif.get("Creator", "")).upper()
                
                if "CAMSCANNER" in txt_lower or "CAMSCANNER" in autor or "CAMSCANNER" in criador:
                    erros.append("Marca d'água / aplicativo de terceiro detectado ('CAMSCANNER'). Fundamento Legal: Art. 4º do Decreto nº 10.278/2020.")

                # Verificação OBRIGATÓRIA de Softwares de Edição Gráfica
                software_usado = (str(metadados_exif.get("Software", "")) + " " + str(metadados_exif.get("Producer", ""))).upper()
                for sw in softwares_suspeitos:
                    if sw in software_usado:
                        erros.append(f"Uso de editor gráfico/software não autorizado detectado ({sw}). Fundamento Legal: Art. 4º do Decreto nº 10.278/2020.")

                doc.close()

                # CORREÇÃO 1: Audita a matriz do Anexo II APENAS se auditar_softwares (auditarMetadados) for True
                matriz_anexo_ii = auditar_metadados_com_metodologia(caminho) if auditar_softwares else []

                resultados.append({
                    "nome": nome_arquivo,
                    "caminho": caminho,
                    "origem": "Nato-Digital" if eh_nato_digital else "Escaneado",
                    "tipo_doc": tipo_documento,
                    "paginas": total_paginas,
                    "dpi": dpi_final_str,
                    "pdfa": eh_pdfa,
                    "modo_cor": modo_cor_final,
                    "colorido": (modo_cor_final == "Colorido"),
                    "hash_sha256": hash_sha256,
                    "aprovado": len(erros) == 0,
                    "erros": erros,
                    "matriz_anexo_ii": matriz_anexo_ii
                })

            except Exception as e:
                resultados.append({
                    "nome": nome_arquivo,
                    "caminho": caminho,
                    "origem": "Erro",
                    "tipo_doc": "Indefinido",
                    "paginas": 0,
                    "dpi": "N/A",
                    "pdfa": False,
                    "modo_cor": "Indefinido",
                    "colorido": False,
                    "hash_sha256": hash_sha256,
                    "aprovado": False,
                    "erros": [f"Falha ao processar o ficheiro PDF: {str(e)}"],
                    "matriz_anexo_ii": []
                })

        return resultados

    def gerar_laudo_pdf(self, resultados):
        """Gera o laudo oficial em PDF em conformidade estrita com o Decreto nº 10.278/2020."""
        try:
            file_type = webview.FileDialog.SAVE if hasattr(webview, 'FileDialog') else webview.SAVE_DIALOG
            local_salvar = self._window.create_file_dialog(
                file_type, 
                save_filename="Laudo_Conformidade_MEC.pdf",
                file_types=('Arquivos PDF (*.pdf)',)
            )
            if not local_salvar:
                return False

            if isinstance(local_salvar, tuple):
                local_salvar = local_salvar[0]

            doc = SimpleDocTemplate(
                local_salvar, 
                pagesize=letter, 
                rightMargin=28, 
                leftMargin=28, 
                topMargin=28, 
                bottomMargin=28
            )
            story = []
            styles = getSampleStyleSheet()

            COR_BORDO = colors.HexColor("#4A1525")
            COR_VERMELHO = colors.HexColor("#D33833")
            COR_VERDE = colors.HexColor("#15803D")
            COR_TEXTO = colors.HexColor("#2D3748")
            COR_FUNDO_ALT = colors.HexColor("#F8FAFC")

            title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=13, textColor=COR_BORDO, spaceAfter=2)
            sub_title = ParagraphStyle('SubTitle', parent=styles['Heading2'], fontSize=10, textColor=COR_BORDO, spaceBefore=10, spaceAfter=4)
            sub_style = ParagraphStyle('SubStyle', parent=styles['Normal'], fontSize=8, textColor=COR_TEXTO, spaceAfter=8)
            
            cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=7, leading=9, textColor=COR_TEXTO)
            cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=7, leading=9, fontName="Helvetica-Bold", textColor=COR_TEXTO)
            cell_header = ParagraphStyle('CellHeader', parent=styles['Normal'], fontSize=7, leading=9, fontName="Helvetica-Bold", textColor=colors.white)

            data_hora = datetime.datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
            story.append(Paragraph("LAUDO TÉCNICO DE CONFORMIDADE REGULATÓRIA - MEC", title_style))
            story.append(Paragraph(f"<b>Data da Auditoria:</b> {data_hora} | <b>Embasamento Legal:</b> Decreto Federal nº 10.278/2020", sub_style))

            total = len(resultados)
            aprovados = sum(1 for r in resultados if r['aprovado'])
            reprovados = total - aprovados

            summary_data = [
                [Paragraph("<b>TOTAL ANALISADO</b>", cell_bold), Paragraph("<b>APROVADOS</b>", cell_bold), Paragraph("<b>REPROVADOS</b>", cell_bold)],
                [Paragraph(str(total), cell_bold), Paragraph(f"<font color='#15803D'>{aprovados}</font>", cell_bold), Paragraph(f"<font color='#D33833'>{reprovados}</font>", cell_bold)]
            ]
            t_summary = Table(summary_data, colWidths=[185, 185, 186])
            t_summary.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COR_FUNDO_ALT),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e0')),
                ('PADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(t_summary)

            # -------------------------------------------------------------------------
            # CORREÇÃO 2: TABELA DE AVALIAÇÃO TÉCNICA (ANEXO I - DPI, PDF/A, COR, PARECER)
            # -------------------------------------------------------------------------
            story.append(Spacer(1, 10))
            story.append(Paragraph("Anexo I (Decreto nº 10.278/2020) - Avaliação de Requisitos Técnicos", sub_title))

            rows_tec = [
                [Paragraph("Arquivo / Tipo", cell_header), 
                 Paragraph("DPI", cell_header), 
                 Paragraph("PDF/A", cell_header), 
                 Paragraph("Cor", cell_header), 
                 Paragraph("Parecer Técnico", cell_header)]
            ]

            for r in resultados:
                status_txt = "<font color='#15803D'><b>APROVADO</b></font>" if r['aprovado'] else "<font color='#D33833'><b>REPROVADO</b></font>"
                pdfa_txt = "Sim" if r['pdfa'] else "Não"
                info_doc = f"<b>{r['nome']}</b><br/>Origem: {r['origem']} | Tipo: {r['tipo_doc']}"
                
                parecer_muda = f"<b>Status:</b> {status_txt}"
                if r.get('erros'):
                    erros_str = "<br/>".join([f"• {e}" for e in r['erros']])
                    parecer_muda += f"<br/><font color='#D33833'>{erros_str}</font>"

                rows_tec.append([
                    Paragraph(info_doc, cell_style),
                    Paragraph(str(r['dpi']), cell_style),
                    Paragraph(pdfa_txt, cell_style),
                    Paragraph(r['modo_cor'], cell_style),
                    Paragraph(parecer_muda, cell_style)
                ])

            t_tec = Table(rows_tec, colWidths=[176, 50, 45, 65, 220])
            t_tec.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), COR_BORDO),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 3),
            ]))
            story.append(t_tec)

            # -------------------------------------------------------------------------
            # CORREÇÃO 3: ANEXO II E NOTA METODOLÓGICA GERADOS APENAS SE HOUVER METADADOS AUDITADOS
            # -------------------------------------------------------------------------
            tem_metadados = any(r.get("matriz_anexo_ii") for r in resultados)

            if tem_metadados:
                story.append(Spacer(1, 10))
                story.append(Paragraph("Anexo II (Decreto nº 10.278/2020) - Matriz Complementar de Metadados", sub_title))

                for r in resultados:
                    if r.get("matriz_anexo_ii"):
                        rows_meta = [
                            [Paragraph("Metadado Exigido (Anexo II - Parte A)", cell_header), 
                             Paragraph("Valor Registrado / Atribuído", cell_header), 
                             Paragraph("Parecer da Auditoria", cell_header)]
                        ]
                        
                        for item in r["matriz_anexo_ii"]:
                            rows_meta.append([
                                Paragraph(f"<b>{item['campo']}</b>", cell_bold),
                                Paragraph(item['valor'], cell_style),
                                Paragraph(item['parecer'], cell_style)
                            ])

                        story.append(Spacer(1, 4))
                        story.append(Paragraph(f"<b>Arquivo: {r['nome']}</b>", cell_style))
                        story.append(Spacer(1, 2))
                        
                        t_meta = Table(rows_meta, colWidths=[130, 180, 246])
                        t_meta.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), COR_BORDO),
                            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('PADDING', (0, 0), (-1, -1), 3),
                        ]))
                        story.append(t_meta)

                # Apêndice Técnico - Nota Metodológica
                story.append(PageBreak())
                story.append(Paragraph("APÊNDICE TÉCNICO - NOTA METODOLÓGICA", title_style))
                story.append(Paragraph("Detalhamento da metodologia de extração e validação dos metadados estruturados exigidos pelo Anexo II do Decreto nº 10.278/2020.", sub_style))
                story.append(Spacer(1, 8))

                nota_metodologica_data = [
                    [Paragraph("Metadado Exigido", cell_header), Paragraph("Origem Sistêmica & Metodologia de Obtenção / Auditoria", cell_header)],
                    [Paragraph("<b>Assunto</b>", cell_bold), Paragraph("Inspecionado nativamente nas propriedades 'keywords' e 'subject' do PDF. Se ausente, é reportado como 'Ausente'.", cell_style)],
                    [Paragraph("<b>Autor (nome)</b>", cell_bold), Paragraph("Lido da propriedade nativa 'author'. Notifica aviso se for detectado nome genérico/usuário de máquina local.", cell_style)],
                    [Paragraph("<b>Data/Local da digitalização</b>", cell_bold), Paragraph("Data/hora extraídas do campo 'creationDate' e convertidas para DD/MM/AAAA. Local indicado como 'Ausente' (não mantido em PDF físico).", cell_style)],
                    [Paragraph("<b>Identificador do documento</b>", cell_bold), Paragraph("Atribuição reservada ao sistema de negócios (Unimestre) via UUID no banco de dados.", cell_style)],
                    [Paragraph("<b>Responsável pela digitalização</b>", cell_bold), Paragraph("Indicação de operador/unidade a ser vinculada no momento do envio ao Unimestre.", cell_style)],
                    [Paragraph("<b>Título</b>", cell_bold), Paragraph("Lido do campo nativo 'title'. Se ausente, adota-se o nome do arquivo como Título Atribuído.", cell_style)],
                    [Paragraph("<b>Tipo documental</b>", cell_bold), Paragraph("Atribuído via taxonomia de catálogo do Unimestre após recepção.", cell_style)],
                    [Paragraph("<b>Hash (checksum) da imagem</b>", cell_bold), Paragraph("Calculado via algoritmo criptográfico SHA-256 diretamente sobre os bytes do arquivo.", cell_style)],
                ]

                t_nota = Table(nota_metodologica_data, colWidths=[140, 416])
                t_nota.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), COR_BORDO),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('PADDING', (0, 0), (-1, -1), 4),
                ]))
                story.append(t_nota)

            doc.build(story)
            return True
        except Exception as e:
            print(f"Erro ao gerar laudo PDF: {str(e)}")
            return False


# ==============================================================================
# PONTO DE ENTRADA E INICIALIZAÇÃO DA INTERFACE
# ==============================================================================
if __name__ == '__main__':
    api = ApiValidador()
    caminho_html = os.path.join(BASE_DIR, 'index.html')

    window = webview.create_window(
        'Validador de Conformidade MEC - Decreto 10.278/2020',
        url=caminho_html,
        js_api=api,
        width=1100,
        height=750,
        resizable=True
    )
    api.set_window(window)
    webview.start(debug=False)