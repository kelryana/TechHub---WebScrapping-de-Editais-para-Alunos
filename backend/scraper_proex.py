import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
from datetime import datetime
from pdf_utils import extrair_data_vencimento_hibrido, verificar_status

#CONSTANTES
MONGODB_URI = "mongodb://localhost:27017/"
NOME_BANCO = "hub_estudantes"
NOME_COLECAO = "vagas_bolsa"
TIMEOUT_PDF = 15  # segundos
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

#FUNÇÕES AUXILIARES
def conectar_banco():
    """Conecta ao MongoDB e retorna a coleção de bolsas"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client[NOME_BANCO]
        return db[NOME_COLECAO]
    except Exception as e:
        print(f"❌ Erro ao conectar ao MongoDB: {e}")
        raise

def completar_url(url_base: str, url_relativa: str) -> str:
    """Completa URLs relativas"""
    if not url_relativa:
        return None
    
    if url_relativa.startswith("http"):
        return url_relativa
    
    if url_relativa.startswith("//"):
        return "https:" + url_relativa
    
    if url_relativa.startswith("/"):
        from urllib.parse import urlparse
        parsed = urlparse(url_base)
        return f"{parsed.scheme}://{parsed.netloc}{url_relativa}"
    
    if url_base.endswith("/"):
        return url_base + url_relativa
    else:
        return url_base + "/" + url_relativa

def limpar_texto(texto: str) -> str:
    """Remove espaços extras e caracteres indesejados"""
    if not texto:
        return ""
    return " ".join(texto.split()).strip()

def encontrar_titulo_edital(container, url_base):
    """
    Encontra o título do edital procurando em elementos anteriores
    
    Returns:
        Tuple (titulo, link_pdf) ou (None, None)
    """
    if container:
        # Tentar encontrar qualquer texto antes do link
        irmao = container.find_previous_sibling()
        texto_temp = ""
        
        while irmao:
            # Ignorar tags vazias ou com apenas espaço
            texto = irmao.get_text(strip=True)
            if texto:
                texto_temp = texto
                break
            irmao = irmao.find_previous_sibling()
        
        # Se não encontrou irmão, tentar pegar o texto do próprio container
        if not texto_temp:
            texto_temp = container.get_text(strip=True)
        
        # Se encontrou, retorna o título e a URL do PDF
        if texto_temp:
            link_pdf = None
            for a in container.find_all('a'):
                href = a.get('href', '')
                if href and (href.lower().endswith('.pdf') or 'edital' in href.lower()):
                    link_pdf = completar_url(url_base, href)
                    break
            
            # Se não achou PDF no container, tenta no irmão
            if not link_pdf and irmao:
                for a in irmao.find_all('a'):
                    href = a.get('href', '')
                    if href and (href.lower().endswith('.pdf') or 'edital' in href.lower()):
                        link_pdf = completar_url(url_base, href)
                        break
            
            return texto_temp, link_pdf
    
    return None, None

def raspar_pagina_proex(url: str, colecao_bd):
    """
    Raspa a página da PROEX em busca de editais de bolsa
    
    Args:
        url: URL da página
        colecao_bd: Coleção do MongoDB
    """
    print(f"\n🔍 Acessando página PROEX: {url}")
    print("="*50)
    
    try:
        resposta = requests.get(url, headers=HEADERS, timeout=30)
        resposta.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"❌ Timeout ao acessar {url}")
        return
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar {url}: {e}")
        return
    
    soup = BeautifulSoup(resposta.text, 'html.parser')
    
    # Estatísticas
    total_editais = 0
    editais_vigentes = 0
    editais_vencidos = 0
    editais_sem_data = 0
    erros = 0
    
    for tag_link in soup.find_all('a'):
        try:
            # Ignorar menus, cabeçalhos, rodapés
            if tag_link.find_parent(['nav', 'aside', 'footer', 'header']):
                continue
            
            texto_link = tag_link.get_text(strip=True).upper()
            
            # Só aceita links com texto exato "EDITAL"
            if texto_link != "EDITAL":
                continue
            
            # Descobre o container do link
            parent = tag_link.parent
            container = parent.parent if parent and parent.name == 'li' else parent
            
            titulo, link_pdf = encontrar_titulo_edital(container, url)
            
            # Se não encontrou título, tentar com o próprio texto do link
            if not titulo:
                titulo = "Edital PROEX"
                print(f"   ⚠️  Título não encontrado, usando padrão")
            
            # Se não encontrou PDF, usar o href do link atual
            if not link_pdf:
                link_pdf = tag_link.get('href')
                if link_pdf:
                    link_pdf = completar_url(url, link_pdf)
            
            # Validação final
            if not link_pdf:
                print(f"   ❌ Link inválido, ignorando")
                erros += 1
                continue
            
            # Filtrar: só aceita se o título começar com "EDITAL"
            if not titulo.upper().strip().startswith("EDITAL"):
                print(f"   ⚠️  Título não começa com 'EDITAL': {titulo[:30]}...")
                continue
    
            # Pegar texto do container para extração HTML
            texto_html = ""
            if container:
                texto_html = container.get_text(strip=True)
            else:
                texto_html = titulo
            
            # Usar função híbrida do pdf_utils
            data_vencimento = extrair_data_vencimento_hibrido(
                texto_html=texto_html,
                url_pdf=link_pdf
            )
            
            # Verificar status usando a função do pdf_utils
            status_vigencia = verificar_status(data_vencimento)
            
            # Log do resultado
            print(f"\n📄 {titulo[:60]}...")
            if data_vencimento:
                print(f"   📅 Data: {data_vencimento} ({status_vigencia})")
            else:
                print(f"   ❓ Sem data ({status_vigencia})")
            
            # Atualizar estatísticas
            if status_vigencia == "vigente":
                editais_vigentes += 1
            elif status_vigencia == "vencido":
                editais_vencidos += 1
            else:
                editais_sem_data += 1
 
            documento = {
                "nome": limpar_texto(titulo),
                "link": link_pdf,
                "categoria": "Bolsa",  # Fixo para PROEX
                "fonte": "PROEX/UERN",
                "data_vencimento": data_vencimento,  # String YYYY-MM-DD
                "status_vigencia": status_vigencia,
                "url_pagina": url,  # Guardar a página original
                "ultima_atualizacao": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Usar link como chave única
            colecao_bd.update_one(
                {"link": link_pdf},
                {"$set": documento},
                upsert=True
            )
            total_editais += 1
            print(f"   💾 Salvo no banco")
            
        except Exception as e:
            print(f"   ❌ Erro ao processar edital: {e}")
            erros += 1
    
    #RELATÓRIO
    print(f"\n{'='*50}")
    print(f"📊 RESUMO PROEX")
    print(f"{'='*50}")
    print(f"  ✅ VIGENTES:   {editais_vigentes}")
    print(f"  ⚠️  VENCIDOS:    {editais_vencidos}")
    print(f"  ❓ SEM DATA:   {editais_sem_data}")
    print(f"  ❌ ERROS:      {erros}")
    print(f"  📊 TOTAL:      {total_editais}")
    print(f"{'='*50}\n")

def executar_scraper_proex(paginas=None):
    """
    Executa o scraper da PROEX
    
    Args:
        paginas: Lista de URLs para raspar (usar padrão se None)
    """
    print("🚀 Iniciando Scraper PROEX")
    print("="*50)
    
    # Conectar ao banco
    colecao = conectar_banco()
    
    # Páginas padrão
    if paginas is None:
        paginas = [
            "https://portal.uern.br/proex/2026-2/"
            # Adicione mais URLs se necessário
        ]
    
    for pagina in paginas:
        raspar_pagina_proex(pagina, colecao)
    
    print("✅ Scraper PROEX finalizado!")

if __name__ == "__main__":
    executar_scraper_proex()