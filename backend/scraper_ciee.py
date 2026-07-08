from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
from pymongo import MongoClient
import time

def conectar_banco():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["hub_estudantes"]
    return db["vagas_ciee"]

def raspar_ciee():
    print("Iniciando robô do CIEE...")
    print("ATENÇÃO: O navegador Firefox vai abrir. Você terá 20 SEGUNDOS para digitar 'Mossoró', apertar Enter e esperar as vagas carregarem!")
    
    firefox_options = Options()
    # Deixa o navegador visível para você interagir
    
    servico = Service(GeckoDriverManager().install())
    navegador = webdriver.Firefox(service=servico, options=firefox_options)
    
    navegador.get("https://portal.ciee.org.br/")
    
    print("\n[TEMPO] O relógio está correndo! Faça a pesquisa por Mossoró no navegador agora...")
    time.sleep(20) 
    print("[ROBO] O robô acordou! Extraindo os dados da tela atual...")
    
    colecao_bd = conectar_banco()
    vagas_inseridas = 0
    
    try:
        botoes = navegador.find_elements(By.XPATH, "//*[contains(text(), 'Ver detalhes')]")
        print(f"-> O robô visualizou {len(botoes)} vagas na tela. Iniciando extração...")
        
        cards_processados = set()
        
        for botao in botoes:
            try:
                card = botao.find_element(By.XPATH, "./ancestor::*[contains(., 'Compartilhar')][1]")
                texto_card = card.text
                
                if texto_card in cards_processados:
                    continue
                cards_processados.add(texto_card)
                
                linhas = [linha.strip() for linha in texto_card.split('\n') if linha.strip()]
                
                nome = "Vaga CIEE"
                categoria = "Estágio/Jovem Aprendiz"
                salario = "A combinar"
                area = "Área não especificada"
                codigo_vaga = "N/A"
                
                for i, linha in enumerate(linhas):
                    if linha.isdigit() and len(linha) >= 5:
                        codigo_vaga = linha
                    elif linha in ["Estágio", "Aprendiz"]:
                        nome = linha
                        if i + 1 < len(linhas):
                            categoria = linhas[i+1]
                    elif "R$" in linha:
                        salario = linha
                    elif "00:00" not in linha and "Mossoró" not in linha and "Compartilhar" not in linha and "Ver detalhes" not in linha:
                        if linha != nome and linha != categoria and len(linha) > 4 and not linha.isdigit():
                            area = linha

                documento = {
                    "nome": f"[{codigo_vaga}] {nome} - {area} ({salario})", 
                    "link": "https://portal.ciee.org.br/", 
                    "categoria": categoria,
                    "fonte": "CIEE"
                }
                
                colecao_bd.update_one(
                    {"nome": documento["nome"]}, 
                    {"$set": documento},
                    upsert=True
                )
                vagas_inseridas += 1
                
            except Exception:
                continue
                
    except Exception as e:
        print(f"Erro principal: {e}")
            
    print(f"\nSucesso! {vagas_inseridas} vagas do CIEE inseridas.")
    navegador.quit()

if __name__ == "__main__":
    raspar_ciee()