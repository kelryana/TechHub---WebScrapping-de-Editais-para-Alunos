##backend/scraper_proex.py
import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
from datetime import datetime

def conectar_banco():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["hub_estudantes"]
    return db["vagas_bolsa"]

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

def raspar_pagina_proex(url, colecao_bd):
    print(f"Acessando a página da PROEX: {url}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    resposta = requests.get(url, headers=headers)

    if resposta.status_code != 200:
        print(f"Erro ao acessar a página. Código: {resposta.status_code}")
        return

    soup = BeautifulSoup(resposta.text, 'html.parser')
    editais_inseridos = 0
    editais_vencidos = 0

    # Estratégia PROEX: Procura diretamente os links <a>
    for tag_link in soup.find_all('a'):
        # Ignora menus laterais, cabeçalhos e rodapés
        if tag_link.find_parent(['nav', 'aside', 'footer', 'header']):
            continue

        texto_link = tag_link.get_text(strip=True).upper()

        # Verifica se o link é literalmente a palavra "EDITAL" (como na imagem em rosa)
        if texto_link == "EDITAL":
            link_pdf = tag_link.get('href')

            # Validação básica do link
            if not link_pdf or link_pdf == "#" or not link_pdf.startswith("http"):
                continue

            # Descobre o elemento "container" do link.
            # Pode ser o item da lista (<li>) ou apenas o parágrafo (<p>)
            parent = tag_link.parent
            container = parent.parent if parent.name == 'li' else parent

            # Procura o título do edital "olhando para cima" (elementos anteriores)
            # Usamos um while para pular parágrafos vazios ou quebras de linha (<br>)
            irmao = container.find_previous_sibling()
            texto_titulo = ""

            while irmao:
                texto_temp = irmao.get_text(strip=True)
                if texto_temp: # Achou o primeiro elemento acima que tem algum texto
                    texto_titulo = texto_temp
                    break
                irmao = irmao.find_previous_sibling()

            # ==========================================
            # FILTRO: Só aceita se o TÍTULO começar com "EDITAL"
            # Isso ignora coisas como "CHAMAMENTO..." ou "NORMAS..."
            # ==========================================
            if not texto_titulo.upper().startswith("EDITAL"):
                continue

            nome_edital = texto_titulo.strip()

            # ==========================================
            # NOVO: Extrair data de vencimento do texto
            # ==========================================
            data_vencimento = extrair_data_vencimento(texto_titulo)
            status_vigencia = "vigente"

            if data_vencimento:
                hoje = datetime.now()
                if data_vencimento < hoje:
                    status_vigencia = "vencido"
                    editais_vencidos += 1
                    print(f"   ⚠️  VENCIDO: {nome_edital[:60]}... (venceu em {data_vencimento.strftime('%d/%m/%Y')})")
                else:
                    print(f"   ✅ VIGENTE: {nome_edital[:60]}... (vence em {data_vencimento.strftime('%d/%m/%Y')})")

            # Monta o documento conforme as suas restrições
            documento = {
                "nome": nome_edital,
                "link": link_pdf,
                "categoria": "Bolsa", # Valor fixo para a PROEX conforme solicitado
                "fonte": "PROEX/UERN",
                "data_vencimento": data_vencimento,
                "status_vigencia": status_vigencia
            }

            # Salva no banco de dados
            colecao_bd.update_one(
                {"link": link_pdf},
                {"$set": documento},
                upsert=True
            )
            editais_inseridos += 1

    print(f"\nResumo PROEX:")
    print(f"  ✅ {editais_inseridos - editais_vencidos} editais VIGENTES")
    print(f"  ⚠️  {editais_vencidos} editais VENCIDOS")
    print(f"  📊 Total: {editais_inseridos} editais processados.\n")

if __name__ == "__main__":
    colecao = conectar_banco()

    # Lista de páginas alvo da PROEX
    paginas_alvo_proex = [
        "https://portal.uern.br/proex/2026-2/"
    ]

    for pagina in paginas_alvo_proex:
        raspar_pagina_proex(pagina, colecao)

    print("Finalizado! Verifique o MongoDB Compass.")