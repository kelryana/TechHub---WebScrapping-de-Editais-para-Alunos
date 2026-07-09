import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
from datetime import datetime
from pdf_utils import extrair_data_vencimento_hibrido, verificar_status

MONGODB_URI = "mongodb://localhost:27017/"
NOME_BANCO = "hub_estudantes"
NOME_COLECAO = "vagas_estagio"
TIMEOUT_PDF = 15  # segundos

def conectar_banco():
    """Conecta ao MongoDB e retorna a coleção de estágios"""
    try:
        client = MongoClient(MONGODB_URI)
        db = client[NOME_BANCO]
        return db[NOME_COLECAO]
    except Exception as e:
        print(f"❌ Erro ao conectar ao MongoDB: {e}")
        raise

def limpar_texto(texto: str) -> str:
    """Remove textos indesejados e limpa o nome do edital"""
    if not texto:
        return ""
    
    # Remove textos comuns
    remover = ["(Clique Aqui)", "(Clique aqui)", "(clique aqui)", "Clique Aqui", "Clique aqui"]
    for item in remover:
        texto = texto.replace(item, "")
    
    # Remove espaços extras
    texto = " ".join(texto.split())
    
    # Remove traço no final
    if texto.endswith("-"):
        texto = texto[:-1].strip()
    
    return texto

def extrair_dados_edital(li, categoria_texto):
    """
    Extrai os dados de um item de lista de edital
    
    Returns:
        dict com nome, link, data_vencimento, status ou None se inválido
    """
    tag_link = li.find('a')
    if not tag_link:
        return None
    
    texto_bruto = li.get_text(strip=True)
    link_pdf = tag_link.get('href')
    
    if not texto_bruto.lower().startswith("edital"):
        return None
    
    # ==========================================
    # FILTRO: Link deve ser válido
    # ==========================================
    if not link_pdf or link_pdf == "#":
        return None
    
    # Completar URL se for relativa
    if not link_pdf.startswith("http"):
        link_pdf = "https://portal.uern.br" + link_pdf
  
    nome_edital = limpar_texto(texto_bruto)
    
    # Usar a função híbrida do pdf_utils
    data_vencimento = extrair_data_vencimento_hibrido(
        texto_html=texto_bruto,
        url_pdf=link_pdf
    )
    
    # Verificar status (vigente/vencido)
    status_vigencia = verificar_status(data_vencimento)
    
    # Log do resultado
    if data_vencimento:
        print(f"   📅 {nome_edital[:50]}... -> {data_vencimento} ({status_vigencia})")
    else:
        print(f"   ❓ {nome_edital[:50]}... -> SEM DATA ({status_vigencia})")
    
    return {
        "nome": nome_edital,
        "link": link_pdf,
        "categoria": categoria_texto,
        "fonte": "PRAE/UERN",
        "data_vencimento": data_vencimento,  # String YYYY-MM-DD
        "status_vigencia": status_vigencia   # "vigente" ou "vencido"
    }

def raspar_pagina_prae(url, colecao_bd):
    """
    Raspa uma página da PRAE em busca de editais
    
    Args:
        url: URL da página
        colecao_bd: Coleção do MongoDB onde salvar
    """
    print(f"\n🔍 Acessando: {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        resposta = requests.get(url, headers=headers, timeout=30)
        resposta.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"❌ Timeout ao acessar {url}")
        return
    except requests.exceptions.RequestException as e:
        print(f"❌ Erro ao acessar {url}: {e}")
        return
    
    soup = BeautifulSoup(resposta.text, 'html.parser')
    
    # Encontrar todas as listas não-navegacionais
    listas_editais = []
    for ul in soup.find_all('ul'):
        # Ignorar listas em menus/navegação
        if ul.find_parent(['nav', 'aside', 'footer', 'header', 'menu']):
            continue
        listas_editais.append(ul)
    
    if not listas_editais:
        print("⚠️ Nenhuma lista encontrada na página")
        return
    
    # Estatísticas
    total_editais = 0
    editais_vigentes = 0
    editais_vencidos = 0
    editais_sem_data = 0
    
    # Processar cada lista
    for ul in listas_editais:
        # Tentar identificar a categoria
        elemento_categoria = ul.find_previous_sibling(['p', 'h2', 'h3', 'h4', 'strong'])
        categoria_texto = "Categoria Geral"
        
        if elemento_categoria:
            categoria_texto = elemento_categoria.get_text(strip=True)
            # Limitar tamanho da categoria
            if len(categoria_texto) > 50:
                categoria_texto = categoria_texto[:47] + "..."
        
        print(f"\n📂 Categoria: {categoria_texto}")
        
        # Processar cada item da lista
        for li in ul.find_all('li', recursive=False):
            dados = extrair_dados_edital(li, categoria_texto)
            if not dados:
                continue
            
            # Salvar no MongoDB (upsert)
            try:
                colecao_bd.update_one(
                    {"link": dados["link"]},
                    {"$set": dados},
                    upsert=True
                )
                total_editais += 1
                
                # Atualizar estatísticas
                if dados["status_vigencia"] == "vigente":
                    editais_vigentes += 1
                elif dados["status_vigencia"] == "vencido":
                    editais_vencidos += 1
                else:
                    editais_sem_data += 1
                    
            except Exception as e:
                print(f"❌ Erro ao salvar edital: {e}")
    
    print(f"\n{'='*50}")
    print(f"📊 RESUMO PRAE")
    print(f"{'='*50}")
    print(f"  ✅ VIGENTES:   {editais_vigentes}")
    print(f"  ⚠️  VENCIDOS:    {editais_vencidos}")
    print(f"  ❓ SEM DATA:   {editais_sem_data}")
    print(f"  📊 TOTAL:      {total_editais}")
    print(f"{'='*50}\n")

def executar_scraper_prae(paginas=None):
    """
    Executa o scraper da PRAE
    
    Args:
        paginas: Lista de URLs para raspar (usar padrão se None)
    """
    print("🚀 Iniciando Scraper PRAE")
    print("="*50)
    
    # Conectar ao banco
    colecao = conectar_banco()
    
    # Páginas a serem raspadas
    if paginas is None:
        paginas = [
            "https://portal.uern.br/prae/2026-2/"
            # Adicione mais URLs aqui se necessário
        ]
    
    # Raspar cada página
    for pagina in paginas:
        raspar_pagina_prae(pagina, colecao)
    
    print("✅ Scraper PRAE finalizado!")

if __name__ == "__main__":
    executar_scraper_prae()