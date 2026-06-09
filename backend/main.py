from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import subprocess
import sys

# Importa a nossa função de raspar na hora
from scraper_noticias import atualizar_noticias_agora

# Cria a aplicação FastAPI
app = FastAPI(title="API TechHub UERN")

# Configuração do CORS (MUITO IMPORTANTE para o Front-end)
# Isso permite que o seu site HTML "puxe" os dados sem dar erro de permissão
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Na fase de testes, permite qualquer origem
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conecta ao MongoDB local
client = MongoClient("mongodb://localhost:27017/")
db = client["hub_estudantes"]

# Rota de teste
@app.get("/")
def raiz():
    return {"mensagem": "A API do TechHub está online! Acesse /docs para testar."}

# Rota para buscar os editais da PRAE
@app.get("/api/estagios")
def listar_estagios():
    colecao = db["vagas_estagio"]
    lista_vagas = []
    
    # Busca todos os documentos na coleção
    for vaga in colecao.find():
        vaga["_id"] = str(vaga["_id"]) # Converte o ObjectId para texto
        lista_vagas.append(vaga)
        
    return lista_vagas

# Rota para buscar as bolsas da PROEX
@app.get("/api/bolsas")
def listar_bolsas():
    colecao = db["vagas_bolsa"]
    lista_bolsas = []
    
    # Busca todos os documentos na coleção
    for bolsa in colecao.find():
        bolsa["_id"] = str(bolsa["_id"]) # Converte o ObjectId para texto
        lista_bolsas.append(bolsa)
        
    return lista_bolsas

@app.get("/api/ufersa")
def listar_ufersa():
    colecao = db["vagas_ufersa"]
    lista_ufersa = []
    
    # Busca todos os documentos na coleção
    for edital in colecao.find():
        edital["_id"] = str(edital["_id"]) # Converte o ObjectId para texto
        lista_ufersa.append(edital)
        
    return lista_ufersa

@app.get("/api/ciee")
def listar_ciee():
    colecao = db["vagas_ciee"]
    lista_ciee = []
    
    # Busca todos os documentos na coleção
    for vaga in colecao.find():
        vaga["_id"] = str(vaga["_id"]) # Converte o ObjectId para texto
        lista_ciee.append(vaga)
        
    return lista_ciee

@app.get("/api/noticias")
def listar_noticias():
    # 1. GATILHO: Roda o script de raspagem ANTES de buscar no banco
    atualizar_noticias_agora()
    
    # 2. Busca os dados que acabaram de ser inseridos
    colecao = db["vagas_noticias"]
    lista_noticias = []
    
    for noticia in colecao.find():
        noticia["_id"] = str(noticia["_id"])
        lista_noticias.append(noticia)
        
    return lista_noticias

# Rota do "Botão Vermelho": Limpa o banco e roda todos os scrapers
@app.get("/api/buscar-tudo")
def acionar_todos_os_robos():
    print("\n[SISTEMA] Iniciando a Varredura Global...")
    
    # 1. Limpa todas as coleções para o "Show" da apresentação
    db["vagas_estagio"].delete_many({})
    db["vagas_bolsa"].delete_many({})
    db["vagas_ufersa"].delete_many({})
    db["vagas_ciee"].delete_many({})
    # db["vagas_noticias"].delete_many({}) -> A de notícias já se auto-limpa no script dela
    
    # Pega o caminho exato do seu Python (para evitar erros de versão)
    python_exe = sys.executable
    
    try:
        # 2. Roda os scripts silenciosos primeiro
        print("-> Raspando PRAE...")
        subprocess.run([python_exe, "scraper_prae.py"])
        
        print("-> Raspando PROEX...")
        subprocess.run([python_exe, "scraper_proex.py"])
        
        print("-> Raspando UFERSA...")
        subprocess.run([python_exe, "scraper_ufersa.py"])
        
        # 3. Roda o CIEE (que vai abrir a tela para você interagir)
        print("-> Raspando CIEE (Atenção ao navegador!)...")
        subprocess.run([python_exe, "scraper_ciee.py"])
        
        # 4. Roda as notícias
        print("-> Raspando Notícias...")
        atualizar_noticias_agora()
        
        return {"mensagem": "Varredura 100% concluída!"}
        
    except Exception as e:
        return {"erro": str(e)}