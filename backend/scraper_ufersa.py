import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import re
from datetime import datetime
from pdf_utils import extrair_data_vencimento_hibrido, verificar_status

MONGODB_URI = "mongodb://localhost:27017/"
NOME_BANCO = "hub_estudantes"
NOME_COLECAO = "vagas_ufersa"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def conectar_banco():
    client = MongoClient(MONGODB_URI)
    db = client[NOME_BANCO]
    return db[NOME_COLECAO]

def extrair_data_completa(texto_html, link_pdf):
    """
    Estratégia híbrida para extrair data de vencimento.
    Retorna string no formato YYYY-MM-DD.
    """
    return extrair_data_vencimento_hibrido(texto_html, link_pdf)

def raspar_lista_ufersa(url_menu, ano_filtro, colecao_bd):
    print(f"Passo 1: Acessando o menu da UFERSA: {url_menu} (Filtro: {ano_filtro})")

    resposta_menu = requests.get(url_menu, headers=HEADERS)
    if resposta_menu.status_code != 200:
        print("Erro ao acessar a página de lista.")
        return

    soup_menu = BeautifulSoup(resposta_menu.text, 'html.parser')

    links_visitados = set()
    editais_inseridos = 0
    editais_vencidos = 0

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
                    resposta_edital = requests.get(url_edital, headers=HEADERS)
                    soup_edital = BeautifulSoup(resposta_edital.text, 'html.parser')

                    nome_edital = texto_link
                    link_pdf = url_edital

                    # Buscar o PDF real
                    for a_pdf in soup_edital.find_all('a'):
                        texto_pdf = a_pdf.get_text(strip=True).upper()
                        href_pdf = a_pdf.get('href', '')

                        if "EDITAL" in texto_pdf and "wp-content/uploads" in href_pdf:
                            link_pdf = href_pdf
                            break

                    data_vencimento = extrair_data_completa(texto_link, link_pdf)

                    status_vigencia = verificar_status(data_vencimento)

                    # Log do resultado
                    if data_vencimento:
                        if status_vigencia == "vencido":
                            editais_vencidos += 1
                            print(f"   ⚠️  VENCIDO: {nome_edital[:60]}... (venceu em {data_vencimento})")
                        else:
                            print(f"   ✅ VIGENTE: {nome_edital[:60]}... (vence em {data_vencimento})")
                    else:
                        print(f"   ❓ SEM DATA: {nome_edital[:60]}...")

                    documento = {
                        "nome": nome_edital,
                        "link": link_pdf,
                        "categoria": "Auxílio/Bolsa",
                        "fonte": "UFERSA",
                        "data_vencimento": data_vencimento,  # String YYYY-MM-DD
                        "status_vigencia": status_vigencia
                    }

                    colecao_bd.update_one(
                        {"link": link_pdf},
                        {"$set": documento},
                        upsert=True
                    )
                    editais_inseridos += 1
                    print("   [Salvo no banco com sucesso]")

                except Exception as e:
                    print(f"   [Erro ao ler a página do edital: {e}]")

    print(f"\nResumo UFERSA:")
    print(f"  ✅ {editais_inseridos - editais_vencidos} editais VIGENTES")
    print(f"  ⚠️  {editais_vencidos} editais VENCIDOS")
    print(f"  📊 Total: {editais_inseridos} editais salvos.\n")

if __name__ == "__main__":
    colecao = conectar_banco()

    url_alvo = "https://proae.ufersa.edu.br/2026-2/"
    ano_desejado = "2026"

    raspar_lista_ufersa(url_alvo, ano_desejado, colecao)