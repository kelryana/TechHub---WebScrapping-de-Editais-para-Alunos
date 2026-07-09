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
                    resposta_edital = requests.get(url_edital, headers=headers)
                    soup_edital = BeautifulSoup(resposta_edital.text, 'html.parser')

                    nome_edital = texto_link
                    link_pdf = url_edital

                    # ==========================================
                    # A MÁGICA ESTÁ AQUI
                    # Restringimos a busca aos links que vão para a pasta de arquivos
                    # ==========================================
                    for a_pdf in soup_edital.find_all('a'):
                        texto_pdf = a_pdf.get_text(strip=True).upper()
                        href_pdf = a_pdf.get('href', '')

                        # Filtro duplo: Tem que ter "EDITAL" no texto E apontar para wp-content/uploads
                        if "EDITAL" in texto_pdf and "wp-content/uploads" in href_pdf:
                            link_pdf = href_pdf
                            break # Achou o PDF real, para o loop!

                    # ==========================================
                    # NOVO: Extrair data de vencimento do texto
                    # ==========================================
                    data_vencimento = extrair_data_vencimento(texto_link)
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
                        "categoria": "Auxílio/Bolsa",
                        "fonte": "UFERSA",
                        "data_vencimento": data_vencimento,
                        "status_vigencia": status_vigencia
                    }

                    colecao_bd.update_one(
                        {"nome": nome_edital},
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