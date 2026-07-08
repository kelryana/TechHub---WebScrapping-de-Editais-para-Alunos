#!/usr/bin/env python3
"""
SCRAPER CIEE HÍBRIDO - Combina extração detalhada + robustez
Autor: TechHub UERN
Versão: 2.0

Características:
- ✅ Busca automática por "Mossoró" (sem intervenção)
- ✅ Modo headless (navegador invisível)
- ✅ Extração detalhada (código, salário, área, etc.)
- ✅ Múltiplas estratégias de busca (fallbacks)
- ✅ Logging estruturado
- ✅ Orientado a objetos
- ✅ Salvamento no MongoDB com deduplicação
"""

import logging
import re
import time
import sys
from datetime import datetime
from pathlib import Path

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
        """
        Inicializa o scraper
        
        Args:
            cidade: Cidade a ser buscada (padrão: Mossoró)
        """
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
            
            # Criar índices para performance
            self.colecao.create_index("codigo", unique=True, sparse=True)
            self.colecao.create_index("link", unique=True, sparse=True)
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
            
            # Modo headless (navegador invisível)
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            
            # User agent realista
            options.set_preference("general.useragent.override",
                "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0")
            
            # Desabilitar imagens para performance
            options.set_preference("permissions.default.image", 2)
            
            # Desabilitar JavaScript (se necessário)
            # options.set_preference("javascript.enabled", False)
            
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=options)
            
            # Timeouts
            self.driver.set_page_load_timeout(30)
            self.driver.implicitly_wait(10)
            
            logger.info("✅ Firefox headless configurado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao configurar driver: {e}")
            return False

    def buscar_cidade(self):
        """
        Busca automaticamente pela cidade usando múltiplas estratégias
        Combina: seu método + meus fallbacks
        """
        try:
            logger.info(f"🔍 Buscando por '{self.cidade}'...")
            
            # ==========================================
            # ESTRATÉGIA 1: Seletor específico (seu método)
            # ==========================================
            campo = None
            
            # Tentar vários seletores (meus fallbacks)
            seletores = [
                # Placeholders
                "//input[contains(@placeholder, 'cid')]",
                "//input[contains(@placeholder, 'Cidade')]",
                "//input[contains(@placeholder, 'local')]",
                "//input[contains(@placeholder, 'Local')]",
                # Tipos
                "//input[@type='text']",
                "//input[@type='search']",
                # Nomes
                "//input[@name='search']",
                "//input[@name='q']",
                "//input[@name='cidade']",
                # Classes comuns
                "//input[contains(@class, 'search')]",
                "//input[contains(@class, 'busca')]",
            ]
            
            for xpath in seletores:
                try:
                    campo = WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    if campo and campo.is_enabled() and campo.is_displayed():
                        logger.info(f"✅ Campo encontrado: {xpath}")
                        break
                except:
                    continue
            
            # ==========================================
            # ESTRATÉGIA 2: Fallback (qualquer input)
            # ==========================================
            if not campo:
                logger.warning("⚠️ Nenhum seletor específico funcionou, tentando fallback...")
                try:
                    inputs = self.driver.find_elements(By.TAG_NAME, "input")
                    for inp in inputs:
                        if (inp.is_enabled() and inp.is_displayed() and 
                            inp.get_attribute("type") not in ["hidden", "submit", "button"]):
                            campo = inp
                            logger.info("✅ Campo encontrado por fallback")
                            break
                except:
                    pass
            
            if not campo:
                logger.error("❌ Campo de busca não encontrado")
                # Salvar screenshot para debug
                self.driver.save_screenshot(f"ciee_sem_campo_{self.session_id}.png")
                return False
            
            # ==========================================
            # DIGITAR E BUSCAR (seu método)
            # ==========================================
            campo.clear()
            campo.send_keys(self.cidade)
            time.sleep(0.5)
            campo.send_keys(Keys.RETURN)
            
            # Aguardar resultados carregarem
            time.sleep(3)
            
            logger.info("✅ Busca realizada com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na busca: {e}")
            return False

    def extrair_vagas(self):
        """
        Extrai vagas usando a lógica específica do seu código
        (extração detalhada de código, salário, área)
        """
        try:
            logger.info("📊 Extraindo vagas...")
            
            # ==========================================
            # SEU MÉTODO: Botões "Ver detalhes"
            # ==========================================
            try:
                botoes = self.driver.find_elements(
                    By.XPATH, "//*[contains(text(), 'Ver detalhes')]"
                )
                logger.info(f"📌 Encontrados {len(botoes)} botões 'Ver detalhes'")
            except:
                logger.warning("⚠️ Não encontrou botões 'Ver detalhes'")
                botoes = []
            
            if not botoes:
                # Tentar encontrar cards de outra forma
                try:
                    cards = self.driver.find_elements(
                        By.XPATH, "//*[contains(@class, 'card') or contains(@class, 'vaga')]"
                    )
                    logger.info(f"📌 Encontrados {len(cards)} cards alternativos")
                    
                    if not cards:
                        self.driver.save_screenshot(f"ciee_sem_vagas_{self.session_id}.png")
                        logger.warning("⚠️ Nenhuma vaga encontrada na página")
                        return False
                except:
                    self.driver.save_screenshot(f"ciee_sem_vagas_{self.session_id}.png")
                    logger.warning("⚠️ Nenhuma vaga encontrada")
                    return False
            
            cards_processados = set()
            
            # Processar cada card
            for i, botao in enumerate(botoes):
                try:
                    # ==========================================
                    # SEU MÉTODO: Subir até o card
                    # ==========================================
                    card = botao.find_element(
                        By.XPATH, "./ancestor::*[contains(., 'Compartilhar')][1]"
                    )
                    
                    texto_card = card.text
                    if texto_card in cards_processados:
                        continue
                    cards_processados.add(texto_card)
                    
                    # ==========================================
                    # SEU MÉTODO: Processar linhas
                    # ==========================================
                    linhas = [linha.strip() for linha in texto_card.split('\n') if linha.strip()]
                    
                    # Valores padrão
                    nome = "Vaga CIEE"
                    categoria = "Estágio/Jovem Aprendiz"
                    salario = "A combinar"
                    area = "Área não especificada"
                    codigo_vaga = "N/A"
                    link = "#"
                    
                    # Extrair informações linha por linha
                    for j, linha in enumerate(linhas):
                        # Código da vaga
                        if linha.isdigit() and len(linha) >= 5:
                            codigo_vaga = linha
                        # Tipo (Estágio/Aprendiz)
                        elif linha in ["Estágio", "Aprendiz"]:
                            nome = linha
                            if j + 1 < len(linhas):
                                categoria = linhas[j + 1]
                        # Salário
                        elif "R$" in linha:
                            salario = linha
                        # Área/Curso
                        elif ("00:00" not in linha and self.cidade not in linha and 
                              "Compartilhar" not in linha and "Ver detalhes" not in linha):
                            if (linha != nome and linha != categoria and 
                                len(linha) > 4 and not linha.isdigit()):
                                area = linha
                    
                    # Extrair link
                    try:
                        link_elem = card.find_element(By.TAG_NAME, "a")
                        link = link_elem.get_attribute("href")
                        if link and not link.startswith("http"):
                            link = f"https://portal.ciee.org.br{link}"
                    except:
                        pass
                    
                    # ==========================================
                    # MEU MÉTODO: Mais campos e estruturação
                    # ==========================================
                    vaga = {
                        # Campos do seu código
                        "codigo": codigo_vaga,
                        "titulo": nome,
                        "categoria": categoria,
                        "salario": salario,
                        "area": area,
                        "nome_completo": f"[{codigo_vaga}] {nome} - {area} ({salario})",
                        
                        # Campos do meu código
                        "link": link or "https://portal.ciee.org.br/",
                        "fonte": "CIEE",
                        "cidade": self.cidade,
                        "coletado_em": datetime.now(),
                        "session_id": self.session_id
                    }
                    
                    # Tentar extrair data de vencimento
                    data_match = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", texto_card)
                    if data_match:
                        vaga["data_vencimento"] = data_match.group(1)
                    
                    # Tentar extrair empresa
                    try:
                        # Procurar por texto que parece nome de empresa
                        for linha in linhas:
                            if any(palavra in linha.lower() for palavra in ["ltda", "s.a", "s/a", "inc.", "corp"]):
                                vaga["empresa"] = linha
                                break
                    except:
                        pass
                    
                    self.vagas.append(vaga)
                    logger.info(f"  ✅ Vaga {i+1}: {vaga['titulo'][:30]} - {vaga['area'][:20]}")
                    
                except Exception as e:
                    logger.debug(f"⚠️ Erro no card {i}: {e}")
                    continue
            
            logger.info(f"📊 Total extraído: {len(self.vagas)} vagas")
            return len(self.vagas) > 0
            
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
                # Usar código como chave única (seu método)
                if vaga.get("codigo") and vaga["codigo"] != "N/A":
                    filtro = {"codigo": vaga["codigo"]}
                # Fallback: usar nome_completo
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
        
        # Detalhes das vagas
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
        
        # Passo 1: Conectar MongoDB
        if not self.conectar_mongodb():
            return False
        
        # Passo 2: Configurar driver
        if not self.configurar_driver():
            return False
        
        try:
            # Passo 3: Acessar site
            logger.info("🌐 Acessando CIEE...")
            self.driver.get(URL_CIEE)
            time.sleep(2)
            
            # Passo 4: Buscar cidade
            if not self.buscar_cidade():
                logger.error("❌ Falha na busca")
                return False
            
            # Passo 5: Extrair vagas
            if not self.extrair_vagas():
                logger.warning("⚠️ Nenhuma vaga extraída")
                return False
            
            # Passo 6: Salvar no MongoDB
            salvos = self.salvar_mongodb()
            
            # Passo 7: Relatório
            self.gerar_relatorio()
            
            logger.info("=" * 60)
            logger.info(f"✅ SCRAPER CONCLUÍDO COM SUCESSO!")
            logger.info(f"   📊 {len(self.vagas)} vagas extraídas")
            logger.info(f"   💾 {salvos} vagas salvas")
            logger.info("=" * 60)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro durante execução: {e}")
            # Salvar screenshot de erro
            try:
                self.driver.save_screenshot(f"ciee_erro_{self.session_id}.png")
                logger.info("📸 Screenshot de erro salvo")
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
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scraper CIEE Híbrido')
    parser.add_argument('--cidade', default='Mossoró', 
                       help='Cidade para buscar (padrão: Mossoró)')
    parser.add_argument('--debug', action='store_true',
                       help='Ativa modo debug (mais logs)')
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    scraper = ScraperCIEEHibrido(cidade=args.cidade)
    sucesso = scraper.executar()
    
    return 0 if sucesso else 1

if __name__ == "__main__":
    exit(main())