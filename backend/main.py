from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo import MongoClient
import subprocess
import sys
import re
from datetime import datetime, timedelta

# Importa a função de raspagem assíncrona de notícias original
from scraper_noticias import atualizar_noticias_agora

app = FastAPI(title="API TechHub UERN")

# Configuração do CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = MongoClient("mongodb://localhost:27017/")
db = client["hub_estudantes"]


# ====================================================================
# INFRAESTRUTURA DE BANCO: NORMALIZAÇÃO E RESOLUÇÃO DE FONTES
# ====================================================================
def garantir_metadados_fontes():
    """
    Abordagem Híbrida NoSQL: Mantém uma coleção normatizada contendo a governança,
    links oficiais e metadados de cada portal institucional parceiro.
    """
    colecao = db["fontes_provedores"]

    # Dicionário mestre de metadados das instituições de Mossoró e região
    fontes_mestre = [
        {
            "_id": "prae_uern",
            "nome_oficial": "Pró-Reitoria de Assuntos Estudantis - UERN",
            "url_oficial": "https://prae.uern.br",
            "frequencia_monitoramento": "Diário",
            "foco_vagas": "Estágios Acadêmicos, Residência e Auxílios Financeiros"
        },
        {
            "_id": "proex_uern",
            "nome_oficial": "Pró-Reitoria de Extensão - UERN",
            "url_oficial": "https://proex.uern.br",
            "frequencia_monitoramento": "Diário",
            "foco_vagas": "Bolsas de Extensão, Cultura e Projetos de Pesquisa"
        },
        {
            "_id": "ufersa_oficial",
            "nome_oficial": "Portal de Editais - UFERSA",
            "url_oficial": "https://ufersa.edu.br",
            "frequencia_monitoramento": "A cada 12 hours",
            "foco_vagas": "Editais de Concursos, Estágios e Assistência Estudantil"
        },
        {
            "_id": "ciee_agente",
            "nome_oficial": "Centro de Integração Empresa-Escola (CIEE)",
            "url_oficial": "https://web.ciee.org.br",
            "frequencia_monitoramento": "A cada 6 hours",
            "foco_vagas": "Vagas de Estágio Comercial e Jovem Aprendiz Técnico"
        },
        # ADIÇÃO ESTRATÉGICA: Vinculo relacional para a nova esteira de dados
        {
            "_id": "portal_uern_oficial",
            "nome_oficial": "Portal UERN - Text Mining",
            "url_oficial": "https://portal.uern.br",
            "frequencia_monitoramento": "Diário",
            "foco_vagas": "Editais Internos Filtrados por Inteligência de Mineração"
        }
    ]

    for fonte in fontes_mestre:
        # Usa upsert para garantir que os links oficiais se mantenham atualizados sem duplicar registros
        colecao.update_one({"_id": fonte["_id"]}, {"$set": fonte}, upsert=True)

# Inicializa as tabelas de metadados mestre na subida do servidor
garantir_metadados_fontes()


def resolver_vinculo_fonte(documento: dict):
    """
    Executa a junção lógica baseada em referência (DBRef Manual) em tempo
    de execução, agregando os metadados ricos da instituição ao edital.
    """
    if not documento:
        return documento

    fonte_id = documento.get("fonte_id")
    if fonte_id:
        fonte_meta = db["fontes_provedores"].find_one({"_id": fonte_id})
        if fonte_meta:
            # Acopla dinamicamente os metadados ricos estruturados para consumo do front-end
            documento["meta_fonte"] = {
                "nome_oficial": fonte_meta.get("nome_oficial"),
                "url_oficial": fonte_meta.get("url_oficial"),
                "frequencia": fonte_meta.get("frequencia_monitoramento")
            }
    return documento


# ====================================================================
# FUNÇÃO AUXILIAR: INTELIGÊNCIA ARTIFICIAL BASEADA EM REGEX (DATA CLEANSING)
# ====================================================================
def extrair_e_converter_data(texto: str) -> datetime:
    if not texto:
        return None
    padrao_data = r"\b(\d{2})/(\d{2})/(\d{4})\b"
    resultado = re.search(padrao_data, texto)
    if resultado:
        dia, mes, ano = resultado.groups()
        try:
            return datetime(int(ano), int(mes), int(dia))
        except ValueError:
            return None
    return None


# Rota de teste
@app.get("/")
def raiz():
    return {"mensagem": "A API do TechHub está online! Acesse /docs para testar."}


# ====================================================================
# ROTAS COM PAGINAÇÃO ATIVA E RESOLUÇÃO DE FONTES INTEGRADA
# ====================================================================

@app.get("/api/estagios")
def listar_estagios(pagina: int = Query(1, ge=1), limite: int = Query(6, ge=1)):
    colecao = db["vagas_estagio"]
    pulo = (pagina - 1) * limite

    lista_vagas = []
    for vaga in colecao.find().skip(pulo).limit(limite):
        vaga["_id"] = str(vaga["_id"])
        if isinstance(vaga.get("data_vencimento"), datetime):
            vaga["data_vencimento_formatada"] = vaga["data_vencimento"].strftime("%d/%m/%Y")

        # Injeta os metadados normatizados da PRAE no JSON de saída
        vaga = resolver_vinculo_fonte(vaga)
        lista_vagas.append(vaga)

    return {
        "pagina_atual": pagina,
        "limite_por_pagina": limite,
        "total_documentos": colecao.count_documents({}),
        "dados": lista_vagas
    }

@app.get("/api/bolsas")
def listar_bolsas(pagina: int = Query(1, ge=1), limite: int = Query(6, ge=1)):
    colecao = db["vagas_bolsa"]
    pulo = (pagina - 1) * limite

    lista_bolsas = []
    for bolsa in colecao.find().skip(pulo).limit(limite):
        bolsa["_id"] = str(bolsa["_id"])
        if isinstance(bolsa.get("data_vencimento"), datetime):
            bolsa["data_vencimento_formatada"] = bolsa["data_vencimento"].strftime("%d/%m/%Y")

        bolsa = resolver_vinculo_fonte(bolsa)
        lista_bolsas.append(bolsa)

    return {
        "pagina_atual": pagina,
        "limite_por_pagina": limite,
        "total_documentos": colecao.count_documents({}),
        "dados": lista_bolsas
    }

@app.get("/api/ufersa")
def listar_ufersa(pagina: int = Query(1, ge=1), limite: int = Query(6, ge=1)):
    colecao = db["vagas_ufersa"]
    pulo = (pagina - 1) * limite

    lista_ufersa = []
    for edital in colecao.find().skip(pulo).limit(limite):
        edital["_id"] = str(edital["_id"])
        if isinstance(edital.get("data_vencimento"), datetime):
            edital["data_vencimento_formatada"] = edital["data_vencimento"].strftime("%d/%m/%Y")

        edital = resolver_vinculo_fonte(edital)
        lista_ufersa.append(edital)

    return {
        "pagina_atual": pagina,
        "limite_por_pagina": limite,
        "total_documentos": colecao.count_documents({}),
        "dados": lista_ufersa
    }

@app.get("/api/ciee")
def listar_ciee(pagina: int = Query(1, ge=1), limite: int = Query(6, ge=1)):
    colecao = db["vagas_ciee"]
    pulo = (pagina - 1) * limite

    lista_ciee = []
    for vaga in colecao.find().skip(pulo).limit(limite):
        vaga["_id"] = str(vaga["_id"])
        
        # 🔧 NORMALIZAÇÃO: Criar campo "nome" esperado pelo frontend
        vaga["nome"] = vaga.get("nome_completo") or vaga.get("titulo") or "Vaga CIEE"
        
        if isinstance(vaga.get("data_vencimento"), datetime):
            vaga["data_vencimento_formatada"] = vaga["data_vencimento"].strftime("%d/%m/%Y")

        vaga = resolver_vinculo_fonte(vaga)
        lista_ciee.append(vaga)

    return {
        "pagina_atual": pagina,
        "limite_por_pagina": limite,
        "total_documentos": colecao.count_documents({}),
        "dados": lista_ciee
    }


# ====================================================================
# ENDPOINT DE CONTINGÊNCIA: CARREGAMENTO DE COORDENADAS MINERADAS UERN
# ====================================================================
@app.get("/api/portal_uern")
def listar_portal_uern(pagina: int = Query(1, ge=1), limite: int = Query(6, ge=1)):
    colecao = db["vagas_portal_uern"]
    pulo = (pagina - 1) * limite

    lista_portal = []
    for edital in colecao.find().skip(pulo).limit(limite):
        edital["_id"] = str(edital["_id"])
        if isinstance(edital.get("data_vencimento"), datetime):
            edital["data_vencimento_formatada"] = edital["data_vencimento"].strftime("%d/%m/%Y")

        edital = resolver_vinculo_fonte(edital)
        lista_portal.append(edital)

    return {
        "pagina_atual": pagina,
        "limite_por_pagina": limite,
        "total_documentos": colecao.count_documents({}),
        "dados": lista_portal
    }


@app.get("/api/noticias")
def listar_noticias(pagina: int = Query(1, ge=1), limite: int = Query(6, ge=1)):
    colecao_cache = db["controle_cache"]
    ultimo_registro = colecao_cache.find_one({"tipo": "noticias"})

    tempo_limite = datetime.now() - timedelta(minutes=10)

    if not ultimo_registro or ultimo_registro["data_execucao"] < tempo_limite:
        print("[CACHE] Cache expirado ou inexistente. A acionar robô de notícias...")
        atualizar_noticias_agora()

        colecao_cache.update_one(
            {"tipo": "noticias"},
            {"$set": {"data_execucao": datetime.now()}},
            upsert=True
        )
    else:
        print("[CACHE] Dados recuperados localmente via cache ativo do MongoDB.")

    colecao = db["vagas_noticias"]
    pulo = (pagina - 1) * limite

    lista_noticias = []
    for noticia in colecao.find().skip(pulo).limit(limite):
        noticia["_id"] = str(noticia["_id"])
        lista_noticias.append(noticia)

    return {
        "pagina_atual": pagina,
        "limite_por_pagina": limite,
        "total_documentos": colecao.count_documents({}),
        "dados": lista_noticias
    }


# ==========================================
# RECURSOS DE INFRAESTRUTURA & PESQUISA
# ==========================================

@app.get("/api/pesquisar")
def pesquisar_unificado(termo: str = Query(..., min_length=2)):
    colecoes = ["vagas_estagio", "vagas_bolsa", "vagas_ufersa", "vagas_ciee", "vagas_portal_uern"]
    resultados = []
    for col_name in db.list_collection_names():
        if col_name in colecoes:
            try:
                cursor = db[col_name].find({"$text": {"$search": termo}})
                for doc in cursor:
                    doc["_id"] = str(doc["_id"])
                    doc = resolver_vinculo_fonte(doc)
                    resultados.append(doc)
            except Exception:
                cursor = db[col_name].find({"nome": {"$regex": termo, "$options": "i"}})
                for doc in cursor:
                    doc["_id"] = str(doc["_id"])
                    doc = resolver_vinculo_fonte(doc)
                    resultados.append(doc)
    return resultados


@app.get("/api/estatisticas")
def obter_estatisticas():
    totais = {
        "estagios": db["vagas_estagio"].count_documents({}),
        "bolsas": db["vagas_bolsa"].count_documents({}),
        "ufersa": db["vagas_ufersa"].count_documents({}),
        "ciee": db["vagas_ciee"].count_documents({}),
        "noticias": db["vagas_noticias"].count_documents({}),
        "portal_uern": db["vagas_portal_uern"].count_documents({}) # Alimentação do novo contador do card
    }

    agora = datetime.now()
    janela_limite = agora + timedelta(days=7)

    query_reta_final = {
        "data_vencimento": {
            "$gte": agora,
            "$lte": janela_limite
        }
    }

    total_reta_final = (
        db["vagas_estagio"].count_documents(query_reta_final) +
        db["vagas_bolsa"].count_documents(query_reta_final) +
        db["vagas_ufersa"].count_documents(query_reta_final) +
        db["vagas_ciee"].count_documents(query_reta_final)
    )

    pipeline_prae = [
        {"$group": {"_id": "$categoria", "total": {"$sum": 1}}},
        {"$sort": {"total": -1}}
    ]
    distribuicao_prae = list(db["vagas_estagio"].aggregate(pipeline_prae))
    formatar = lambda lista: [{"categoria": item["_id"] if item["_id"] else "Geral / Não Especificada", "total": item["total"]} for item in lista]

    return {
        "totais": totais,
        "reta_final_urgente": total_reta_final,
        "prae_categorias": formatar(distribuicao_prae)
    }


@app.get("/api/db-status")
def obter_status_do_banco():
    status_colecoes = []
    # Adicionado vagas_portal_uern para auditoria transparente
    colecoes = ["vagas_estagio", "vagas_bolsa", "vagas_ufersa", "vagas_ciee", "vagas_noticias", "vagas_portal_uern", "historico_varreduras", "fontes_provedores"]

    for col_name in colecoes:
        colecao = db[col_name]
        try:
            indices_brutos = list(colecao.list_indexes())
            indices_nomes = [idx["name"] for idx in indices_brutos]
        except Exception:
            indices_nomes = ["_id_"]

        try:
            stats = db.command("collStats", col_name)
            tamanho_kb = round(stats.get("size", 0) / 1024, 2)
            documentos_qtd = stats.get("count", 0)
        except Exception:
            tamanho_kb = 0.0
            documentos_qtd = colecao.count_documents({})

        has_validator = False
        try:
            col_info = db.command("listCollections", filter={"name": col_name})["cursor"]["firstBatch"]
            if col_info and "options" in col_info[0] and "validator" in col_info[0]["options"]:
                has_validator = True
        except Exception:
            pass

        status_colecoes.append({
            "colecao": col_name,
            "documentos": documentos_qtd,
            "tamanho_kb": tamanho_kb,
            "indices": indices_nomes,
            "has_validator": has_validator
        })

    return {
        "banco": "hub_estudantes",
        "host": "MongoDB Local (localhost:27017)",
        "colecoes": status_colecoes
    }


# ====================================================================
# SCRIPT DE EXECUÇÃO GLOBAL INTEGRADO (PRESERVA SISTEMA ANTIGO RÁPIDO)
# ====================================================================
@app.get("/api/buscar-tudo")
def acionar_todos_os_robos():
    print("\n[SISTEMA] Iniciando a Varredura Global de Infraestrutura...")

    inicio_varredura = datetime.now()

    db["vagas_estagio"].delete_many({})
    db["vagas_bolsa"].delete_many({})
    db["vagas_ufersa"].delete_many({})
    db["vagas_ciee"].delete_many({})

    python_exe = sys.executable
    status_final = "Sucesso"
    detalhe_erro = None

    try:
        print("-> A raspar PRAE...")
        subprocess.run([python_exe, "scraper_prae.py"])

        print("-> A raspar PROEX...")
        subprocess.run([python_exe, "scraper_proex.py"])

        print("-> A raspar UFERSA...")
        subprocess.run([python_exe, "scraper_ufersa.py"])

        print("-> A raspar CIEE...")
        subprocess.run([python_exe, "scraper_ciee.py"])

        print("-> A raspar Notícias...")
        atualizar_noticias_agora()

        # NOTA TÉCNICA: A coleção 'vagas_portal_uern' é alimentada de forma assíncrona 
        # via script de sementes (popular_portal.py) para contornar bloqueios do Cloudflare.

        # ------------------------------------------------------------
        # PIPELINE DE HIGIENIZAÇÃO E CRUZA DE REFERÊNCIAS NOSQL
        # ------------------------------------------------------------
        print("[MIGRAÇÃO] Rodando Normalização Heurística de Dados...")

        # Mapeia qual coleção pertence a qual chave identificadora de fonte
        mapeamento_fontes = {
            "vagas_estagio": "prae_uern",
            "vagas_bolsa": "proex_uern",
            "vagas_ufersa": "ufersa_oficial",
            "vagas_ciee": "ciee_agente",
            "vagas_portal_uern": "portal_uern_oficial"
        }

        for col_name, id_fonte in mapeamento_fontes.items():
            cursor = db[col_name].find()
            for doc in cursor:
                texto_alvo = f"{doc.get('nome', '')} {doc.get('categoria', '')}"
                data_detectada = extrair_e_converter_data(texto_alvo)

                # Monta a carga de atualização injetando a chave estrangeira (Referência)
                payload_atualizacao = {"fonte_id": id_fonte}
                if data_detectada:
                    payload_atualizacao["data_vencimento"] = data_detectada

                db[col_name].update_one(
                    {"_id": doc["_id"]},
                    {"$set": payload_atualizacao}
                )

    except Exception as e:
        status_final = "Erro"
        detalhe_erro = str(e)

    fim_varredura = datetime.now()
    log_auditoria = {
        "data_execucao": inicio_varredura,
        "tempo_duracao_segundos": round((fim_varredura - inicio_varredura).total_seconds(), 2),
        "status": status_final,
        "erro": detalhe_erro,
        "documentos_importados": {
            "estagios": db["vagas_estagio"].count_documents({}),
            "bolsas": db["vagas_bolsa"].count_documents({}),
            "ufersa": db["vagas_ufersa"].count_documents({}),
            "noticias": db["vagas_noticias"].count_documents({}),
            "portal_uern": db["vagas_portal_uern"].count_documents({})
        }
    }

    db["historico_varreduras"].insert_one(log_auditoria)

    if status_final == "Erro":
        return {"erro": detalhe_erro}