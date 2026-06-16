from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
import time

PALAVRAS_CHAVE = [
    "estágio", "estágios", "bolsa", "bolsas", "vaga", "vagas", 
    "seleção", "edital", "pnaes", "auxílio", "residência", "monitoria",
    "inscrições", "cursos", "vagas abertas"
]

def analisar_conteudo(texto):
    """Varre o texto da notícia e conta as palavras-chave encontradas."""
    if not texto:
        return None
    
    texto_minusculo = texto.lower()
    ocorrencias = []
    
    for palavra in PALAVRAS_CHAVE:
        if palavra in texto_minusculo:
            qtd = texto_minusculo.count(palavra)
            ocorrencias.append(f"'{palavra}' ({qtd}x)")
            
    if ocorrencias:
        return ", ".join(ocorrencias)
    return None

def criar_navegador_real():
    opcoes = Options()
    opcoes.add_argument("--headless")  # Roda oculto em segundo plano
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-dev-shm-usage")
    opcoes.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=opcoes)

def minerar_profundo_noticias():
    print("\n🕵️‍♂️ [DEEP MINING] Inicializando ambiente de mineração textual...")
    driver = criar_navegador_real()
    
    try:
        print("\n🌐 Passo 1: Capturando links de notícias no Portal da UERN...")
        driver.get("https://portal.uern.br/todas-as-noticias/")
        time.sleep(6) # Tempo para o servidor responder
        
        soup_principal = BeautifulSoup(driver.page_source, "html.parser")
        links_ancora = soup_principal.find_all("a")
        
        # Filtra apenas links legítimos de matérias do blog
        urls_noticias = []
        for ancora in links_ancora:
            url = ancora.get("href", "")
            if "portal.uern.br/blog/" in url and url not in urls_noticias:
                urls_noticias.append(url)
                
        print(f"🎯 Mapeamento concluído! {len(urls_noticias)} notícias prontas para análise profunda.")
        print("-" * 70)
        
        # Passo 2: O robô entra em cada notícia mapeada
        for i, url_interna in enumerate(urls_noticias[:5], start=1): # Limitado a 5 para o teste não ficar exaustivo
            print(f"\n🚀 [{i}/{len(urls_noticias)}] Entrando na notícia: {url_interna}")
            
            driver.get(url_interna)
            time.sleep(4) # Espera carregar o corpo do texto da matéria
            
            soup_interna = BeautifulSoup(driver.page_source, "html.parser")
            
            # Captura o título real interno da matéria
            titulo_h1 = soup_interna.find("h1")
            titulo_real = titulo_h1.get_text().strip() if titulo_h1 else "Título não identificado"
            
            # Pega todos os parágrafos do texto da notícia
            paragrafos = soup_interna.find_all("p")
            texto_completo = " ".join([p.get_text() for p in paragrafos])
            
            # Executa a Mineração de Texto
            resultado_analise = analisar_conteudo(texto_completo)
            
            if resultado_analise:
                print(f"    🔥 OPORTUNIDADE DETECTADA INTERNAMENTE!")
                print(f"    📝 Título: {titulo_real}")
                print(f"    📊 Métricas encontradas: {resultado_analise}")
                print(f"    📏 Volume de dados analisados: {len(texto_completo)} caracteres.")
            else:
                print(f"    ❌ Notícia '{titulo_real}' lida por completo. Sem palavras-chave relevantes. Descartada.")
                
    except Exception as e:
        print(f"❌ Ocorreu um erro na mineração: {e}")
    finally:
        driver.quit()
        print("\n🔒 Processo encerrado e navegador fechado com segurança.")

if __name__ == "__main__":
    print("🤖=== INICIANDO VARREDURA DE TEXT MINING NA UERN ===")
    minerar_profundo_noticias()
    print("🤖=== PROTOCOLO FINALIZADO ===")