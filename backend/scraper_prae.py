#backend/scraper_prae.py 
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
    if not texto:
        return None

    padroes = [
        r"\b(\d{2})/(\d{2})/(\d{4})\b",
        r"\b(\d{1,2})\s*[-/]\s*(\d{1,2})\s*[-/]\s*(\d{4})\b",
    ]

    for padrao in padroes:
        match = re.search(padrao, texto)
        if match:
            try:
                dia, mes, ano = int(match.group(1)), int(match.group(2)), int(match.group(3))
                data = datetime(ano, mes, dia)
                if data >= datetime.now():
                    return data
            except ValueError:
                continue
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

    listas_editais = soup.find_all('ul')
    editais_inseridos = 0

    for ul in listas_editais:
        if ul.find_parent(['nav', 'aside', 'footer', 'header']):
            continue

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

            if not texto_bruto.lower().startswith("edital"):
                continue

            if link_pdf == "#" or not link_pdf.startswith("http"):
                continue

            nome_edital = texto_bruto.replace("(Clique Aqui)", "").replace("(Clique aqui)", "").strip()
            if nome_edital.endswith("-"):
                nome_edital = nome_edital[:-1].strip()

            data_vencimento = extrair_data_vencimento(texto_bruto)

            if not data_vencimento:
                texto_completo = f"{nome_edital} {categoria_texto}"
                data_vencimento = extrair_data_vencimento(texto_completo)

            documento = {
                "nome": nome_edital,
                "link": link_pdf,
                "categoria": categoria_texto,
                "fonte": "PRAE/UERN"
            }

            if data_vencimento:
                documento["data_vencimento"] = data_vencimento

            colecao_bd.update_one(
                {"link": link_pdf},
                {"$set": documento},
                upsert=True
            )
            editais_inseridos += 1

    print(f"Sucesso! {editais_inseridos} editais oficiais processados nesta página.\n")

if __name__ == "__main__":
    colecao = conectar_banco()

    # A lista onde você coloca as páginas específicas que quer ler
    paginas_alvo = [
        "https://portal.uern.br/prae/2026-2/"
    ]

    for pagina in paginas_alvo:
        raspar_pagina_prae(pagina, colecao)

    print("Finalizado! Verifique o MongoDB Compass.")