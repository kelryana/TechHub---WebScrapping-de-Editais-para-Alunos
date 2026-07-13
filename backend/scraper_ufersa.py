##backend/scraper_ufersa.py 

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
from datetime import datetime

def conectar_banco():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["hub_estudantes"]
    return db["vagas_ufersa"]

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
                return data
            except ValueError:
                continue
    return None

def raspar_lista_ufersa(url_menu, ano_filtro, colecao_bd):
    print(f"Passo 1: Acessando o menu da UFERSA: {url_menu} (Filtro: {ano_filtro})")
    headers = {'User-Agent': 'Mozilla/5.0'}

    resposta_menu = requests.get(url_menu, headers=headers)
    if resposta_menu.status_code != 200:
        print("Erro ao acessar a página de lista.")
        return

    soup_menu = BeautifulSoup(resposta_menu.text, 'html.parser')

    links_visitados = set()
    editais_inseridos = 0

    for tag_a in soup_menu.find_all('a'):
        texto_link = tag_a.get_text(strip=True)
        url_edital = tag_a.get('href')

        if not url_edital or url_edital == "#" or not url_edital.startswith("http"):
            continue

        if texto_link.lower().startswith("edital") and ano_filtro in texto_link:

            if url_edital not in links_visitados:
                links_visitados.add(url_edital)
                print(f"\n-> Encontrou: {texto_link[:50]}...")

                try:
                    resposta_edital = requests.get(url_edital, headers=headers)
                    soup_edital = BeautifulSoup(resposta_edital.text, 'html.parser')

                    nome_edital = texto_link
                    link_pdf = url_edital

                    for a_pdf in soup_edital.find_all('a'):
                        texto_pdf = a_pdf.get_text(strip=True).upper()
                        href_pdf = a_pdf.get('href', '')

                        if "EDITAL" in texto_pdf and "wp-content/uploads" in href_pdf:
                            link_pdf = href_pdf
                            break

                    data_vencimento = extrair_data_vencimento(nome_edital)

                    documento = {
                        "nome": nome_edital,
                        "link": link_pdf,
                        "categoria": "Auxílio/Bolsa",
                        "fonte": "UFERSA"
                    }

                    if data_vencimento:
                        documento["data_vencimento"] = data_vencimento

                    colecao_bd.update_one(
                        {"nome": nome_edital},
                        {"$set": documento},
                        upsert=True
                    )
                    editais_inseridos += 1
                    print("   [Salvo no banco com sucesso]")

                except Exception as e:
                    print(f"   [Erro ao ler a página do edital: {e}]")

    print(f"\nFinalizado! {editais_inseridos} editais da UFERSA salvos.")

if __name__ == "__main__":
    colecao = conectar_banco()

    url_alvo = "https://proae.ufersa.edu.br/2026-2/"
    ano_desejado = "2026"

    raspar_lista_ufersa(url_alvo, ano_desejado, colecao)