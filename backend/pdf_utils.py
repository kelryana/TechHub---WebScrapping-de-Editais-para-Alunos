"""
Utilitários para extração de texto e datas de arquivos PDF.
Usa pdfminer.six para extração robusta de texto.
Estratégia híbrida: HTML (rápido) -> PDF (preciso)
"""

import requests
import re
from datetime import datetime
from io import BytesIO
import os
import hashlib
from typing import Optional, Tuple

try:
    from pdfminer.high_level import extract_text
    PDFMINER_AVAILABLE = True
except ImportError:
    PDFMINER_AVAILABLE = False
    print("⚠️  pdfminer.six não disponível. Instale com: pip install pdfminer.six")


_CACHE_PDF = {}
_MAX_CACHE = 50  # Limitar cache para não consumir muita memória


def _cache_pdf(url: str, conteudo: BytesIO) -> None:
    """Armazena PDF em cache"""
    if len(_CACHE_PDF) >= _MAX_CACHE:
        # Remove o item mais antigo
        _CACHE_PDF.pop(next(iter(_CACHE_PDF)))
    _CACHE_PDF[url] = conteudo


def _obter_cache_pdf(url: str) -> Optional[BytesIO]:
    """Recupera PDF do cache"""
    if url in _CACHE_PDF:
        # Resetar posição do BytesIO
        _CACHE_PDF[url].seek(0)
        return _CACHE_PDF[url]
    return None


def baixar_pdf(url: str, timeout: int = 15, usar_cache: bool = True) -> Optional[BytesIO]:
    """
    Baixa um PDF de uma URL e retorna o conteúdo como bytes.

    Args:
        url: URL do PDF
        timeout: Timeout em segundos (padrão: 15s)
        usar_cache: Se deve usar cache (padrão: True)

    Returns:
        BytesIO com o conteúdo do PDF ou None se falhar
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    # Verificar cache primeiro
    if usar_cache:
        cacheado = _obter_cache_pdf(url)
        if cacheado:
            print(f"   📦 PDF do cache: {url[:80]}...")
            return cacheado

    try:
        print(f"   📥 Baixando PDF: {url[:80]}...")
        resposta = requests.get(url, headers=headers, timeout=timeout, stream=True)

        if resposta.status_code == 200:
            # Verifica se é realmente um PDF
            content_type = resposta.headers.get('Content-Type', '').lower()
            if 'application/pdf' in content_type or url.lower().endswith('.pdf'):
                conteudo = BytesIO(resposta.content)
                
                # Salvar no cache
                if usar_cache:
                    _cache_pdf(url, BytesIO(resposta.content))  # Salva uma cópia
                
                print(f"   ✅ PDF baixado com sucesso ({len(resposta.content)} bytes)")
                return conteudo
            else:
                print(f"   ⚠️  URL não retorna PDF (Content-Type: {content_type})")
                return None
        else:
            print(f"   ❌ Erro ao baixar PDF: Status {resposta.status_code}")
            return None

    except requests.exceptions.Timeout:
        print(f"   ⏱️  Timeout ao baixar PDF ({timeout}s)")
        return None
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Erro de rede ao baixar PDF: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Erro inesperado ao baixar PDF: {e}")
        return None


def extrair_texto_pdf(arquivo_pdf_bytes: BytesIO, max_paginas: int = 10) -> str:
    """
    Extrai texto de um arquivo PDF.

    Args:
        arquivo_pdf_bytes: BytesIO com o conteúdo do PDF
        max_paginas: Número máximo de páginas a extrair (0 = todas)

    Returns:
        String com o texto extraído ou string vazia se falhar
    """
    if not PDFMINER_AVAILABLE:
        print("   ⚠️  pdfminer.six não disponível")
        return ""

    try:
        # Extrair texto completo
        texto = extract_text(arquivo_pdf_bytes)
        
        # Limitar número de páginas se especificado
        if max_paginas > 0:
            # Extrair apenas as primeiras páginas
            from pdfminer.pdfpage import PDFPage
            from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
            from pdfminer.converter import TextConverter
            from pdfminer.layout import LAParams
            
            arquivo_pdf_bytes.seek(0)
            resource_manager = PDFResourceManager()
            output = BytesIO()
            converter = TextConverter(resource_manager, output, laparams=LAParams())
            interpreter = PDFPageInterpreter(resource_manager, converter)
            
            texto_limitado = ""
            for page_num, page in enumerate(PDFPage.get_pages(arquivo_pdf_bytes, caching=True)):
                if page_num >= max_paginas:
                    break
                interpreter.process_page(page)
                texto_limitado += output.getvalue().decode('utf-8', errors='ignore')
                output.truncate(0)
                output.seek(0)
            
            converter.close()
            texto = texto_limitado if texto_limitado else texto
        
        print(f"   📄 Texto extraído: {len(texto)} caracteres")
        return texto
    except Exception as e:
        print(f"   ❌ Erro ao extrair texto do PDF: {e}")
        return ""


def extrair_data_de_texto(texto: str) -> Optional[str]:
    """
    Extrai data de vencimento de um texto usando múltiplos padrões regex.
    Retorna no formato YYYY-MM-DD para consistência com a API.

    Args:
        texto: Texto onde procurar a data

    Returns:
        String no formato YYYY-MM-DD ou None
    """
    if not texto or len(texto) < 5:
        return None

    # Converter texto para string limpa
    texto = str(texto)
    
    # Lista de padrões em ordem de prioridade
    padroes = [
        # Padrão 1: "até DD/MM/AAAA" - muito comum para prazos
        (r"(?:até|data\s*limite|prazo\s*(?:final|máximo)?|vencimento|inscrições?\s*(?:até|para))\.?\s*:?[\s]*(\d{1,2})/(\d{1,2})/(\d{4})", "normal"),
        
        # Padrão 2: "DD/MM/AAAA a DD/MM/AAAA" - período, pega a segunda data
        (r"(\d{1,2})/(\d{1,2})/(\d{4})\s*(?:a|até|-)\s*(\d{1,2})/(\d{1,2})/(\d{4})", "periodo"),
        
        # Padrão 3: "período DD/MM/AAAA a DD/MM/AAAA"
        (r"(?:período|periodo).*?(\d{1,2})/(\d{1,2})/(\d{4}).*?(\d{1,2})/(\d{1,2})/(\d{4})", "periodo"),
        
        # Padrão 4: "DD/MM/AA" (ano com 2 dígitos)
        (r"(?:até|prazo|vencimento)[\s:]*(\d{1,2})/(\d{1,2})/(\d{2})", "normal_curto"),
        
        # Padrão 5: "DD de Mês de AAAA" (formato textual)
        (r"(\d{1,2})\s+de\s+(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})", "textual"),
        
        # Padrão 6: Data simples isolada (menos prioritário)
        (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "normal"),
    ]

    for padrao, tipo in padroes:
        resultado = re.search(padrao, texto, re.IGNORECASE | re.DOTALL)
        if resultado:
            grupos = resultado.groups()
            
            if tipo == "periodo":
                # Pega a segunda data (fim do período)
                try:
                    dia, mes, ano = int(grupos[3]), int(grupos[4]), int(grupos[5])
                except:
                    continue
            elif tipo == "textual":
                # Converte mês textual para número
                meses = {
                    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
                    'maio': 5, 'junho': 6, 'julho': 7, 'agosto': 8,
                    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12
                }
                try:
                    dia, mes_nome, ano = int(grupos[0]), grupos[1].lower(), int(grupos[2])
                    mes = meses.get(mes_nome, 0)
                    if mes == 0:
                        continue
                except:
                    continue
            elif tipo == "normal_curto":
                # Converte ano com 2 dígitos para 4
                try:
                    dia, mes, ano = int(grupos[0]), int(grupos[1]), int(grupos[2])
                    # Ajuste: se ano < 50, considera 2000+, senão 1900+
                    ano_completo = 2000 + ano if ano < 50 else 1900 + ano
                except:
                    continue
            else:
                # Formato normal DD/MM/AAAA
                try:
                    dia, mes, ano = int(grupos[0]), int(grupos[1]), int(grupos[2])
                except:
                    continue

            try:
                # Validar data
                data_encontrada = datetime(ano, mes, dia)
                
                # Validação: ano entre 2020 e 2035
                if not (2020 <= ano <= 2035):
                    continue
                
                # Verificar se a data é válida (ex: 31/02 é inválido)
                data_encontrada.strftime('%Y-%m-%d')
                
                data_str = data_encontrada.strftime('%Y-%m-%d')
                print(f"   📅 Data encontrada: {data_str}")
                return data_str
                
            except (ValueError, TypeError):
                continue

    return None


def extrair_data_vencimento_pdf(url_pdf: str, timeout: int = 15) -> Optional[str]:
    """
    Baixa um PDF e extrai a data de vencimento.

    Args:
        url_pdf: URL do arquivo PDF
        timeout: Timeout em segundos para download

    Returns:
        String no formato YYYY-MM-DD ou None
    """
    print(f"   🔍 Extraindo data do PDF...")

    # Baixa o PDF
    pdf_bytes = baixar_pdf(url_pdf, timeout)
    if not pdf_bytes:
        return None

    # Extrai o texto (apenas primeiras 5 páginas para performance)
    texto = extrair_texto_pdf(pdf_bytes, max_paginas=5)
    if not texto:
        return None

    # Extrai a data do texto
    data = extrair_data_de_texto(texto)

    if data:
        return data
    else:
        print(f"   ⚠️  Nenhuma data encontrada no PDF")
        return None


def extrair_data_vencimento_hibrido(texto_html: str, url_pdf: str) -> Optional[str]:
    """
    Estratégia híbrida: tenta HTML primeiro (rápido), depois PDF (preciso).

    Args:
        texto_html: Texto extraído do HTML
        url_pdf: URL do PDF

    Returns:
        String no formato YYYY-MM-DD ou None
    """
    # Passo 1: Tentar no HTML
    if texto_html:
        data_html = extrair_data_de_texto(texto_html)
        if data_html:
            print(f"   ✅ Data encontrada no HTML: {data_html}")
            return data_html
    
    # Passo 2: Tentar no PDF
    if url_pdf:
        print(f"   ⏳ Data não encontrada no HTML, usando PDF...")
        data_pdf = extrair_data_vencimento_pdf(url_pdf)
        if data_pdf:
            print(f"   ✅ Data encontrada no PDF: {data_pdf}")
            return data_pdf
    
    print(f"   ⚠️  Nenhuma data encontrada (HTML + PDF)")
    return None


def verificar_status(data_vencimento: Optional[str]) -> str:
    """
    Verifica se a data está vigente ou vencida.

    Args:
        data_vencimento: Data no formato YYYY-MM-DD

    Returns:
        "vigente" ou "vencido"
    """
    if not data_vencimento:
        return "vigente"  # Fallback
    
    try:
        hoje = datetime.now().date()
        data_limite = datetime.strptime(data_vencimento, '%Y-%m-%d').date()
        
        if data_limite >= hoje:
            return "vigente"
        else:
            return "vencido"
    except (ValueError, TypeError):
        return "vigente"


def extrair_e_validar_data(texto_html: str, url_pdf: str) -> Tuple[Optional[str], str]:
    """
    Função principal para ser usada nos scrapers.
    Retorna (data_vencimento, status_vigencia)

    Args:
        texto_html: Texto do HTML
        url_pdf: URL do PDF

    Returns:
        Tupla com (data_vencimento, status_vigencia)
    """
    data = extrair_data_vencimento_hibrido(texto_html, url_pdf)
    status = verificar_status(data)
    return data, status

def limpar_cache_pdf():
    """Limpa o cache de PDFs"""
    global _CACHE_PDF
    _CACHE_PDF = {}
    print("✅ Cache de PDFs limpo")


if __name__ == "__main__":
    # Teste rápido
    print("="*60)
    print("🧪 TESTANDO PDF UTILS")
    print("="*60)
    
    # Teste com texto HTML
    texto_teste = """
    EDITAL Nº 001/2026
    Período de inscrições: 10/01/2026 a 15/02/2026
    Prazo final: 20/02/2026
    """
    
    print("\n🔍 Teste com texto HTML:")
    data = extrair_data_de_texto(texto_teste)
    print(f"   Data extraída: {data}")
    
    # Teste de status
    print("\n🔍 Teste de verificação de status:")
    data_teste = "2024-12-31"
    status = verificar_status(data_teste)
    print(f"   Data {data_teste} -> {status}")
    
    data_teste = "2027-01-01"
    status = verificar_status(data_teste)
    print(f"   Data {data_teste} -> {status}")
    
    print("\n" + "="*60)
    print("✅ Testes concluídos")