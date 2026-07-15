##backend/scraper_portal_uern.py
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import re
import json

# Palavras-chave para filtrar oportunidades relevantes
PALAVRAS_CHAVE_OPORTUNIDADES = [
    "estágio", "estágios", "bolsa", "bolsas", "vaga", "vagas",
    "seleção", "edital", "pnaes", "auxílio", "residência", "monitoria",
    "inscrições", "cursos", "vagas abertas", "processo seletivo",
    "extensão", "pesquisa", "iniciação científica"
]

def extrair_data_do_texto(texto):
    """Tenta extrair uma data do texto para usar como vencimento"""
    if not texto:
        return datetime.now()

    # Padrões comuns de data no Brasil
    padroes = [
        r"\b(\d{2})/(\d{2})/(\d{4})\b",  # DD/MM/YYYY
        r"\b(\d{2})-(\d{2})-(\d{4})\b",  # DD-MM-YYYY
    ]

    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            try:
                g1, g2, g3 = match.groups()
                return datetime(int(g3), int(g2), int(g1))
            except (ValueError, AttributeError):
                pass

    # Se não encontrar data específica, retorna data atual + 7 dias (padrão)
    return datetime.now() + timedelta(days=7)

def analisar_relevancia(texto):
    """Analisa se o conteúdo contém palavras-chave de oportunidade"""
    if not texto:
        return False, []

    texto_lower = texto.lower()
    palavras_encontradas = []

    for palavra in PALAVRAS_CHAVE_OPORTUNIDADES:
        if palavra in texto_lower:
            palavras_encontradas.append(palavra)

    return len(palavras_encontradas) > 0, palavras_encontradas

def criar_navegador_headless():
    """Cria uma instância do Chrome em modo headless com configurações anti-detecção"""
    opcoes = Options()
    opcoes.add_argument("--headless=new")  # Novo modo headless mais moderno
    opcoes.add_argument("--no-sandbox")
    opcoes.add_argument("--disable-dev-shm-usage")
    opcoes.add_argument("--disable-gpu")
    opcoes.add_argument("--window-size=1920,1080")
    opcoes.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
    opcoes.add_argument("--lang=pt-BR")

    # Evitar detecção de automação
    opcoes.add_experimental_option("excludeSwitches", ["enable-automation"])
    opcoes.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opcoes)

    # Executa CDP para remover flags de automação
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['pt-BR', 'pt', 'en']
            });
        """
    })

    return driver

def extrair_data_do_texto(texto):
    """Tenta extrair uma data do texto para usar como vencimento"""
    if not texto:
        return datetime.now()

    # Padrões comuns de data no Brasil
    padroes = [
        r"\b(\d{2})/(\d{2})/(\d{4})\b",  # DD/MM/YYYY
        r"\b(\d{2})-(\d{2})-(\d{4})\b",  # DD-MM-YYYY
        r"\b(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\b"  # DD de Mês de YYYY
    ]

    for padrao in padroes:
        match = re.search(padrao, texto, re.IGNORECASE)
        if match:
            try:
                if len(match.groups()) == 3:
                    g1, g2, g3 = match.groups()
                    if padrao.includes("Mês"):
                        meses = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
                                "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
                                "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12}
                        mes_num = meses.get(g2.lower(), 1)
                        return datetime(int(g3), mes_num, int(g1))
                    else:
                        return datetime(int(g3), int(g2), int(g1))
            except (ValueError, AttributeError):
                pass

    # Se não encontrar data específica, retorna data atual + 7 dias (padrão)
    return datetime.now() + timedelta(days=7)

def analisar_relevancia(texto):
    """Analisa se o conteúdo contém palavras-chave de oportunidade"""
    if not texto:
        return False, []

    texto_lower = texto.lower()
    palavras_encontradas = []

    for palavra in PALAVRAS_CHAVE_OPORTUNIDADES:
        if palavra in texto_lower:
            palavras_encontradas.append(palavra)

    return len(palavras_encontradas) > 0, palavras_encontradas

def minerar_portal_uern():
    """
    Realiza a mineração completa do Portal da UERN, contornando Cloudflare
    e extraindo apenas notícias relevantes para estudantes
    """
    print("\n" + "="*70)
    print("🕵️‍♂️ INICIANDO MINERAÇÃO DO PORTAL UERN (ANTI-CLOUDFLARE)")
    print("="*70)

    colecao = conectar_banco()
    driver = None

    try:
        # Limpa dados antigos
        print("\n🧹 Limpando coleção 'vagas_portal_uern'...")
        colecao.delete_many({})

        # Inicializa navegador
        print("\n🌐 Passo 1: Inicializando navegador Selenium com stealth...")
        driver = criar_navegador_headless()

        # Acessa página principal de notícias
        url_principal = "https://portal.uern.br/todas-as-noticias/"
        print(f"📡 Acessando: {url_principal}")
        driver.get(url_principal)

        # Aguarda carregamento completo (Cloudflare pode demorar)
        print("⏳ Aguardando carregamento (Cloudflare challenge)...")
        time.sleep(8)

        # Rola página para carregar conteúdo dinâmico
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        # Parse do HTML
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # Extrai todos os links de notícias
        print("\n🔗 Passo 2: Mapeando links de notícias...")
        links_ancora = soup.find_all("a", href=True)

        urls_noticias = set()
        for ancora in links_ancora:
            url = ancora.get("href", "")
            # Filtra apenas URLs válidas do blog da UERN
            if "portal.uern.br/blog/" in url and "/blog/" in url:
                # Normaliza URL (remove parâmetros desnecessários)
                url_limpa = url.split("?")[0]
                urls_noticias.add(url_limpa)

        urls_noticias = list(urls_noticias)
        print(f"✅ {len(urls_noticias)} notícias encontradas na página principal")

        # Limita às 15 mais recentes para não sobrecarregar
        urls_para_analisar = urls_noticias[:15]
        print(f"📋 Selecionadas {len(urls_para_analisar)} notícias para análise profunda")

        # Mineração profunda em cada notícia
        noticias_validas = []
        print("\n🔍 Passo 3: Análise profunda de conteúdo (Text Mining)...")

        for i, url_noticia in enumerate(urls_para_analisar, start=1):
            print(f"\n[{i}/{len(urls_para_analisar)}] Analisando: {url_noticia[:60]}...")

            try:
                # Acessa página interna
                driver.get(url_noticia)
                time.sleep(4)  # Aguarda carregamento

                soup_interna = BeautifulSoup(driver.page_source, "html.parser")

                # Extrai título (H1)
                titulo_tag = soup_interna.find("h1")
                titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Título não identificado"

                # Extrai corpo do texto (parágrafos)
                paragrafos = soup_interna.find_all("p")
                texto_completo = " ".join([p.get_text(strip=True) for p in paragrafos])

                # Extrai resumo/meta descrição se disponível
                meta_desc = soup_interna.find("meta", attrs={"name": "description"})
                resumo = meta_desc.get("content", "") if meta_desc else ""

                # Combina título + resumo + texto para análise
                conteudo_analise = f"{titulo} {resumo} {texto_completo[:500]}"

                # Verifica relevância
                eh_relevante, palavras_chave = analisar_relevancia(conteudo_analise)

                if eh_relevante:
                    print(f"   ✅ OPORTUNIDADE DETECTADA!")
                    print(f"   📝 Título: {titulo[:80]}")
                    print(f"   🔑 Palavras-chave: {', '.join(palavras_chave[:5])}")

                    # Extrai data aproximada
                    data_vencimento = extrair_data_do_texto(texto_completo)

                    # Determina categoria baseada nas palavras-chave
                    categoria = "Notícia Geral"
                    if any(p in palavras_chave for p in ["estágio", "vaga", "seleção"]):
                        categoria = "Seleção de Estágio"
                    elif any(p in palavras_chave for p in ["bolsa", "bolsas", "extensão", "pesquisa"]):
                        categoria = "Bolsas e Editais"
                    elif any(p in palavras_chave for p in ["curso", "inscrição", "matrícula"]):
                        categoria = "Cursos e Inscrições"

                    # Cria documento
                    documento = {
                        "nome": titulo,
                        "link": url_noticia,
                        "categoria": categoria,
                        "fonte_id": "portal_uern_oficial",
                        "data_vencimento": data_vencimento,
                        "palavras_chave": palavras_chave,
                        "resumo": resumo[:200] if resumo else texto_completo[:200],
                        "data_mineracao": datetime.now()
                    }

                    noticias_validas.append(documento)
                else:
                    print(f"   ❌ Não relevante - descartada")

            except Exception as e:
                print(f"   ⚠️ Erro ao processar: {str(e)[:50]}")
                continue

        # Insere no banco
        if noticias_validas:
            print(f"\n💾 Passo 4: Persistindo {len(noticias_validas)} oportunidades no MongoDB...")
            colecao.insert_many(noticias_validas)

            print("\n" + "="*70)
            print(f"✅ SUCESSO! {len(noticias_validas)} oportunidades mineradas e salvas!")
            print("="*70)

            # Mostra resumo
            print("\n📊 RESUMO DAS OPORTUNIDADES:")
            for i, noticia in enumerate(noticias_validas, start=1):
                print(f"  {i}. {noticia['nome'][:70]}...")
                print(f"     Categoria: {noticia['categoria']}")
                print(f"     Link: {noticia['link'][:60]}...")
        else:
            print("\n⚠️ Nenhuma oportunidade relevante encontrada nesta varredura.")
            print("💡 Isso pode ser normal se não houver novas publicações recentes.")

        return len(noticias_validas)

    except Exception as e:
        print(f"\n❌ ERRO CRÍTICO NA MINERAÇÃO: {str(e)}")
        print("💡 Verifique se o ChromeDriver está instalado e acessível.")
        return 0

    finally:
        if driver:
            print("\n🔒 Fechando navegador...")
            driver.quit()

if __name__ == "__main__":
    total = minerar_portal_uern()
    print(f"\n🎯 Total de oportunidades mineradas: {total}")