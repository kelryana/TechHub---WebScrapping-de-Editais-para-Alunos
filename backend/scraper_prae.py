##backend/scraper_prae.py
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
from datetime import datetime

def conectar_banco():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["hub_estudantes"]
    return db["vagas_estagio"]

def extrair_data_vencimento(texto):
    """
    Extrai data de vencimento do texto usando regex.
    Procura padrões como: DD/MM/AAAA
    Retorna objeto datetime ou None se não encontrar.
    """
    if not texto:
        return None

    # Padrão 1: DD/MM/AAAA
    padrao1 = r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b"
    resultado = re.search(padrao1, texto)
    if resultado:
        dia, mes, ano = resultado.groups()
        try:
            return datetime(int(ano), int(mes), int(dia))
        except ValueError:
            pass

    # Padrão 2: "até DD/MM/AAAA" ou "vencimento: DD/MM/AAAA"
    padrao2 = r"(?:até|vencimento|prazo).*?(\d{1,2})/(\d{1,2})/(\d{4})"
    resultado = re.search(padrao2, texto, re.IGNORECASE)
    if resultado:
        dia, mes, ano = resultado.groups()
        try:
            return datetime(int(ano), int(mes), int(dia))
        except ValueError:
            pass

    return None

def raspar_pagina_prae(url, colecao_bd):
    print(f"Acessando a página específica: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    resposta = requests.get(url, headers=headers)

    if resposta.status_code != 200:
        print(f"Erro ao acessar a página. Código: {resposta.status_code}")
        return

    soup = BeautifulSoup(resposta.text, 'html.parser')

    # Pega todas as listas da página
    listas_editais = soup.find_all('ul')
    editais_inseridos = 0
    editais_vencidos = 0

    for ul in listas_editais:
        # Se a lista estiver dentro de um menu de navegação, rodapé ou barra lateral, ignora totalmente
        if ul.find_parent(['nav', 'aside', 'footer', 'header']):
            continue

        # Tenta achar o título da categoria (geralmente o parágrafo ou título acima da lista)
        elemento_categoria = ul.find_previous_sibling(['p', 'h2', 'h3', 'h4', 'strong'])
        categoria_texto = "Categoria Geral"

        if elemento_categoria:
            categoria_texto = elemento_categoria.get_text(strip=True)

        for li in ul.find_all('li'):
            tag_link = li.find('a')
            if not tag_link:
                continue

            texto_bruto = li.get_text(strip=True)
            link_pdf = tag_link.get('href')

            # ==========================================
            # FILTRO CEGO E RIGOROSO
            # Só aceita se o texto começar com a palavra "Edital"
            # O .lower() garante que vai funcionar se estiver escrito "EDITAL", "Edital", "edital"
            # ==========================================
            if not texto_bruto.lower().startswith("edital"):
                continue

            if link_pdf == "#" or not link_pdf.startswith("http"):
                continue
            # ==========================================

            # Limpeza do texto para ficar bonito no banco
            nome_edital = texto_bruto.replace("(Clique Aqui)", "").replace("(Clique aqui)", "").strip()
            if nome_edital.endswith("-"):
                nome_edital = nome_edital[:-1].strip()

            # ==========================================
            # NOVO: Extrair data de vencimento do texto
            # ==========================================
            data_vencimento = extrair_data_vencimento(texto_bruto)
            
            # 🔥 CORRIGIDO: Definir hoje ANTES de usar
            hoje = datetime.now()

            # Determinar status de vigência
            if data_vencimento and data_vencimento < hoje:
                status_vigencia = "vencido"
                editais_vencidos += 1
                print(f"   ⚠️  VENCIDO: {nome_edital[:60]}... (venceu em {data_vencimento.strftime('%d/%m/%Y')})")
            elif data_vencimento:
                status_vigencia = "vigente"
                print(f"   ✅ VIGENTE: {nome_edital[:60]}... (vence em {data_vencimento.strftime('%d/%m/%Y')})")
            else:
                status_vigencia = "vigente"  # Sem data, considerar vigente

            documento = {
                "nome": nome_edital,
                "link": link_pdf,
                "categoria": categoria_texto,
                "fonte": "PRAE/UERN",
                "data_vencimento": data_vencimento,
                "status_vigencia": status_vigencia
            }

            colecao_bd.update_one(
                {"link": link_pdf},
                {"$set": documento},
                upsert=True
            )
            editais_inseridos += 1

    print(f"\nResumo PRAE:")
    print(f"  ✅ {editais_inseridos - editais_vencidos} editais VIGENTES")
    print(f"  ⚠️  {editais_vencidos} editais VENCIDOS")
    print(f"  📊 Total: {editais_inseridos} editais processados.\n")

if __name__ == "__main__":
    colecao = conectar_banco()

    # A lista onde você coloca as páginas específicas que quer ler
    paginas_alvo = [
        "https://portal.uern.br/prae/2026-2/"
    ]

    for pagina in paginas_alvo:
        raspar_pagina_prae(pagina, colecao)

    print("Finalizado! Verifique o MongoDB Compass.")