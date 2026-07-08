#!/usr/bin/env python3
"""
SCRAPER CIEE HÍBRIDO - Combina extração detalhada + robustez
Autor: TechHub UERN
Versão: 2.0
"""

import logging
import re
import time
import sys
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.firefox import GeckoDriverManager
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

# ============================================
# CONFIGURAÇÕES
# ============================================

MONGO_URI = "mongodb://localhost:27017/"
DB_NAME = "hub_estudantes"
COLLECTION_NAME = "vagas_ciee"
CIDADE = "Mossoró"
URL_CIEE = "https://portal.ciee.org.br/"

# ============================================
# LOGGING
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('scraper_ciee.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# SCRAPER
# ============================================

class ScraperCIEEHibrido:
    def __init__(self, cidade=CIDADE):
        self.cidade = cidade
        self.driver = None
        self.vagas = []
        self.colecao = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"🆕 Sessão iniciada: {self.session_id}")
        logger.info(f"🎯 Buscando por: {cidade}")

    def conectar_mongodb(self):
        """Conecta ao MongoDB e prepara a coleção"""
        try:
            client = MongoClient(MONGO_URI)
            db = client[DB_NAME]
            self.colecao = db[COLLECTION_NAME]
            
            # Criar índices para performance (SEM unique no link)
            self.colecao.create_index("codigo", unique=True, sparse=True)
            self.colecao.create_index("link")
            self.colecao.create_index("coletado_em")
            self.colecao.create_index("cidade")
            
            logger.info("✅ Conectado ao MongoDB com índices")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na conexão MongoDB: {e}")
            return False

    def configurar_driver(self):

        """Configura o Firefox em modo headless"""
        try:
            options = Options()
            
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            options.set_preference("general.useragent.override",
                "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0")
            options.set_preference("permissions.default.image", 2)
            
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            
            logger.info("✅ Firefox headless configurado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar driver: {e}")
            return False

    def buscar_cidade(self):
    """Busca pela cidade e CLICA NA SUGESTÃO"""
    try:
        logger.info(f"🔍 Buscando por '{self.cidade}'...")
        
        # Encontrar o campo de busca
        campo = None
        seletores = [
            "//input[contains(@placeholder, 'cidade')]",
            "//input[contains(@placeholder, 'Cidade')]",
            "//input[@type='text']",
        ]
        
        for xpath in seletores:
            try:
                campo = WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                if campo and campo.is_enabled() and campo.is_displayed():
                    logger.info(f"✅ Campo encontrado: {xpath}")
                    break
            except:
                continue
        
        if not campo:
            logger.error("❌ Campo de busca não encontrado")
            return False
        
        # PASSO 1: CLICAR NO CAMPO (ativa o dropdown)
        campo.click()
        time.sleep(0.5)
        
        # PASSO 2: DIGITAR A CIDADE
        campo.clear()
        campo.send_keys(self.cidade)
        logger.info(f"✅ Digitado '{self.cidade}'")
        time.sleep(2)
        
        # PASSO 3: CLICAR NA SUGESTÃO (CORRIGIDO!)
        try:
            sugestao = None
            
            # 🔥 CORRIGIDO: Procurar por "MOSSORÓ - RN" (texto EXATO)
            # O texto da sugestão é "MOSSORÓ - RN" (maiúsculo, com - RN)
            texto_sugestao = f"{self.cidade.upper()} - RN"
            logger.info(f"🔍 Procurando sugestão: '{texto_sugestao}'")
            
            # Estratégia 1: Procurar por <li> com o texto EXATO
            sugestoes = self.driver.find_elements(By.XPATH, 
                f"//li[contains(text(), '{texto_sugestao}')]")
            for elem in sugestoes:
                if elem.is_displayed() and elem.is_enabled():
                    sugestao = elem
                    logger.info("✅ Sugestão encontrada (li)")
                    break
            
            # Estratégia 2: Procurar por ID específico
            if not sugestao:
                try:
                    sugestao = self.driver.find_element(By.ID, "2408003")
                    logger.info("✅ Sugestão encontrada por ID")
                except:
                    pass
            
            # Estratégia 3: Procurar dentro do ComboCidade
            if not sugestao:
                try:
                    sugestao = self.driver.find_element(By.CSS_SELECTOR, "#ComboCidade li")
                    logger.info("✅ Sugestão encontrada por CSS")
                except:
                    pass
            
            if sugestao:
                # Rolar e clicar
                self.driver.execute_script("arguments[0].scrollIntoView(true);", sugestao)
                time.sleep(0.5)
                sugestao.click()
                logger.info(f"✅ Sugestão '{texto_sugestao}' clicada!")
                time.sleep(2)
                
                # PASSO 4: CLICAR NO BOTÃO "Aplicar"
                try:
                    aplicar = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Aplicar')]")
                    aplicar.click()
                    logger.info("✅ Botão 'Aplicar' clicado")
                    time.sleep(2)
                except:
                    pass
                
                # PASSO 5: VERIFICAR SE O FILTRO FUNCIONOU
                time.sleep(2)
                pagina_texto = self.driver.page_source.lower()
                if self.cidade.lower() in pagina_texto:
                    logger.info(f"✅ Busca por '{self.cidade}' confirmada!")
                    
                    # Verificar se há vagas
                    try:
                        botoes = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Ver detalhes')]")
                        logger.info(f"✅ {len(botoes)} vagas encontradas")
                    except:
                        pass
                    
                    return True
                else:
                    logger.warning(f"⚠️ '{self.cidade}' NÃO encontrado após clicar na sugestão")
                    return False
            else:
                logger.warning("⚠️ Nenhuma sugestão encontrada, tentando Enter...")
                campo.send_keys(Keys.RETURN)
                time.sleep(3)
                return True
                    
        except Exception as e:
            logger.error(f"❌ Erro ao clicar na sugestão: {e}")
            campo.send_keys(Keys.RETURN)
            time.sleep(3)
            return True
                
    except Exception as e:
        logger.error(f"❌ Erro na busca: {e}")
        return False

    def extrair_vagas(self):
        """Extrai vagas filtrando por Mossoró"""
        try:
            logger.info("📊 Extraindo vagas...")
            
            # Aguardar carregamento
            time.sleep(3)
            
            # Buscar botões "Ver detalhes"
            try:
                botoes = WebDriverWait(self.driver, 20).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//*[contains(text(), 'Ver detalhes')]"))
                )
                logger.info(f"📌 Encontrados {len(botoes)} botões 'Ver detalhes'")
            except:
                botoes = []
            
            if not botoes:
                logger.warning("⚠️ Nenhum botão 'Ver detalhes' encontrado")
                self.driver.save_screenshot(f"ciee_sem_botoes_{self.session_id}.png")
                return False
            
            cards_processados = set()
            vagas_temp = []
            
            for i, botao in enumerate(botoes):
                try:
                    card = botao.find_element(
                        By.XPATH, "./ancestor::*[contains(., 'Compartilhar')][1]"
                    )
                    
                    texto_card = card.text
                    if texto_card in cards_processados:
                        continue
                    cards_processados.add(texto_card)
                    
                    linhas = [linha.strip() for linha in texto_card.split('\n') if linha.strip()]
                    
                    # Valores padrão
                    nome = "Vaga CIEE"
                    categoria = "Estágio/Jovem Aprendiz"
                    salario = "A combinar"
                    area = "Área não especificada"
                    codigo_vaga = "N/A"
                    link = "#"
                    endereco = ""
                    cidade_encontrada = ""
                    
                    # Extrair código e endereço
                    for j, linha in enumerate(linhas):
                        # Capturar código (número com 6+ dígitos)
                        if linha.isdigit() and len(linha) >= 6:
                            codigo_vaga = linha
                        elif linha in ["Estágio", "Aprendiz"]:
                            nome = linha
                            if j + 1 < len(linhas):
                                categoria = linhas[j + 1]
                        elif "R$" in linha:
                            salario = linha
                        # Capturar endereço que contém a cidade
                        elif self.cidade in linha or "RN" in linha:
                            endereco = linha
                            cidade_encontrada = self.cidade
                        elif ("00:00" not in linha and "Compartilhar" not in linha and "Ver detalhes" not in linha and
                              linha != nome and linha != categoria and len(linha) > 4 and not linha.isdigit()):
                            area = linha
                    
                    # Construir URL a partir do código
                    if codigo_vaga != "N/A":
                        link_detalhe = f"https://portal.ciee.org.br/quero-uma-vaga/?codigoVaga={codigo_vaga}"
                        
                        try:
                            link_elem = card.find_element(By.TAG_NAME, "a")
                            link = link_elem.get_attribute("href")
                            if link:
                                link_detalhe = link
                        except:
                            pass
                        
                        link = link_detalhe
                    else:
                        link = "https://portal.ciee.org.br/"
                    
                    # Montar vaga
                    vaga = {
                        "codigo": codigo_vaga,
                        "titulo": nome,
                        "categoria": categoria,
                        "salario": salario,
                        "area": area,
                        "endereco": endereco,
                        "cidade": cidade_encontrada if cidade_encontrada else self.cidade,
                        "nome_completo": f"[{codigo_vaga}] {nome} - {area} ({salario})",
                        "link": link,
                        "fonte": "CIEE",
                        "coletado_em": datetime.now(),
                        "session_id": self.session_id
                    }
                    
                    # Tentar extrair data
                    data_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", texto_card)
                    if data_match:
                        vaga["data_vencimento"] = data_match.group(1)
                    
                    vagas_temp.append(vaga)
                    
                    # Log com código e endereço
                    endereco_log = vaga['endereco'][:30] if vaga['endereco'] else 'sem endereço'
                    logger.info(f"  📝 Vaga {i+1}: [{codigo_vaga}] {vaga['titulo'][:20]} - {endereco_log}")
                    
                except Exception as e:
                    logger.debug(f"⚠️ Erro no card {i}: {e}")
                    continue
            
            # Filtrar por endereço que contém a cidade
            vagas_filtradas = []
            for vaga in vagas_temp:
                texto_completo = f"{vaga.get('nome_completo', '')} {vaga.get('area', '')} {vaga.get('endereco', '')}"
                if self.cidade in texto_completo or "RN" in texto_completo:
                    vaga["cidade"] = self.cidade
                    vagas_filtradas.append(vaga)
                    logger.info(f"  ✅ Vaga de {self.cidade}: [{vaga['codigo']}] {vaga['titulo'][:20]} - {vaga['endereco'][:30]}")
            
            self.vagas = vagas_filtradas
            
            if not self.vagas:
                logger.warning(f"⚠️ Nenhuma vaga de {self.cidade} encontrada!")
                self.driver.save_screenshot(f"ciee_sem_vagas_{self.cidade}_{self.session_id}.png")
                return False
            
            logger.info(f"📊 Total extraído: {len(self.vagas)} vagas de {self.cidade}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na extração: {e}")
            return False

    def salvar_mongodb(self):
        """Salva as vagas no MongoDB com deduplicação"""
        if not self.vagas:
            logger.warning("⚠️ Nenhuma vaga para salvar")
            return 0
        
        logger.info(f"💾 Salvando {len(self.vagas)} vagas no MongoDB...")
        
        salvos = 0
        atualizados = 0
        erros = 0
        
        for vaga in self.vagas:
            try:
                if vaga.get("codigo") and vaga["codigo"] != "N/A":
                    filtro = {"codigo": vaga["codigo"]}
                else:
                    filtro = {"nome_completo": vaga["nome_completo"]}
                
                resultado = self.colecao.update_one(
                    filtro,
                    {"$set": vaga},
                    upsert=True
                )
                
                if resultado.upserted_id:
                    salvos += 1
                elif resultado.modified_count:
                    atualizados += 1
                    
            except Exception as e:
                logger.warning(f"⚠️ Erro ao salvar vaga: {e}")
                erros += 1
        
        logger.info(f"✅ {salvos} novas vagas salvas, {atualizados} atualizadas")
        if erros > 0:
            logger.warning(f"⚠️ {erros} vagas com erro")
        
        return salvos

    def gerar_relatorio(self):
        """Gera um relatório da execução"""
        logger.info("=" * 60)
        logger.info("📊 RELATÓRIO DE EXECUÇÃO")
        logger.info("=" * 60)
        logger.info(f"🆔 Sessão: {self.session_id}")
        logger.info(f"🏙️  Cidade: {self.cidade}")
        logger.info(f"📊 Vagas extraídas: {len(self.vagas)}")
        logger.info("=" * 60)
        
        for i, vaga in enumerate(self.vagas, 1):
            logger.info(f"{i}. [{vaga.get('codigo', 'N/A')}] {vaga.get('titulo', 'Sem título')}")
            logger.info(f"   📌 Área: {vaga.get('area', 'N/E')}")
            logger.info(f"   💰 Salário: {vaga.get('salario', 'N/I')}")
            if vaga.get('data_vencimento'):
                logger.info(f"   📅 Vence: {vaga['data_vencimento']}")
            logger.info("   ---")

    def executar(self):
        """Executa o scraper completo"""
        logger.info("=" * 60)
        logger.info("🚀 SCRAPER CIEE HÍBRIDO")
        logger.info("=" * 60)
        logger.info(f"📍 Busca por: {self.cidade}")
        logger.info(f"🌐 URL: {URL_CIEE}")
        logger.info("=" * 60)
        
        if not self.conectar_mongodb():
            return False
        
        if not self.configurar_driver():
            return False
        
        try:
            logger.info("🌐 Acessando CIEE...")
            self.driver.get(URL_CIEE)
            time.sleep(2)
            
            if not self.buscar_cidade():
                logger.error("❌ Falha na busca")
                return False
            
            if not self.extrair_vagas():
                logger.warning("⚠️ Nenhuma vaga extraída")
                return False
            
            salvos = self.salvar_mongodb()
            self.gerar_relatorio()
            
            logger.info("=" * 60)
            logger.info(f"✅ SCRAPER CONCLUÍDO COM SUCESSO!")
            logger.info(f"   📊 {len(self.vagas)} vagas extraídas")
            logger.info(f"   💾 {salvos} vagas salvas")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro durante execução: {e}")
            try:
                self.driver.save_screenshot(f"ciee_erro_{self.session_id}.png")
            except:
                pass
            return False
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("🔚 Navegador fechado")

# ============================================
# MAIN
# ============================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper CIEE Híbrido')
    parser.add_argument('--cidade', default='Mossoró', 
                       help='Cidade para buscar (padrão: Mossoró)')
    parser.add_argument('--debug', action='store_true',
                       help='Ativa modo debug')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    scraper = ScraperCIEEHibrido(cidade=args.cidade)
    sucesso = scraper.executar()
    
    return 0 if sucesso else 1

if __name__ == "__main__":
    exit(main())