// URL base da sua API FastAPI
const API_URL = "http://localhost:8000/api";

// Quando a página carregar, puxa os estágios por padrão
window.onload = () => {
    carregarDados('estagios');
};

// --- FUNÇÕES DE BUSCA E NAVEGAÇÃO ---

async function carregarDados(tipo) {
    const container = document.getElementById('container-vagas');
    container.style.display = 'grid'; // Garante o layout grid
    container.innerHTML = '<p class="carregando">Buscando dados no banco...</p>';

    document.querySelectorAll('.controles button').forEach(botao => {
        botao.classList.remove('ativo');
    });
    
    const botaoAtivo = document.getElementById(`btn-${tipo}`);
    if(botaoAtivo) botaoAtivo.classList.add('ativo');

    try {
        const resposta = await fetch(`${API_URL}/${tipo}`);
        const dados = await resposta.json();
        renderizarCards(dados);
    } catch (erro) {
        console.error("Erro ao buscar dados:", erro);
        container.innerHTML = '<p class="carregando" style="color: red;">Erro ao conectar com a API. O FastAPI está rodando?</p>';
    }
}

// 1. NOVA FUNÇÃO: Pesquisa Textual via MongoDB
async function realizarPesquisa() {
    const termo = document.getElementById('input-busca').value;
    if (!termo) return;

    const container = document.getElementById('container-vagas');
    container.innerHTML = '<p class="carregando">Consultando índices no MongoDB...</p>';
    
    try {
        const resposta = await fetch(`${API_URL}/pesquisar?termo=${termo}`);
        const dados = await resposta.json();
        renderizarCards(dados);
    } catch (e) {
        container.innerHTML = '<p class="carregando" style="color: red;">Erro na pesquisa.</p>';
    }
}

// 2. NOVA FUNÇÃO: Painel Analítico (Gráficos)
async function carregarEstatisticas() {
    const container = document.getElementById('container-vagas');
    container.style.display = 'grid';
    container.style.gridTemplateColumns = 'repeat(auto-fit, minmax(250px, 1fr))';
    container.style.gap = '20px';
    container.innerHTML = '<p class="carregando">Processando Dashboard...</p>';

    document.querySelectorAll('.controles button').forEach(b => b.classList.remove('ativo'));
    document.getElementById('btn-analises').classList.add('ativo');

    const res = await fetch(`${API_URL}/estatisticas`);
    const dados = await res.json();

    // Cria cards elegantes para o dashboard
    container.innerHTML = `
        <div class="card" style="border-left: 5px solid var(--laranja);">
            <h3>🏢 Estágios</h3>
            <p style="font-size: 2rem; font-weight: bold;">${dados.totais.estagios}</p>
        </div>
        <div class="card" style="border-left: 5px solid var(--azul-claro);">
            <h3>💰 Bolsas</h3>
            <p style="font-size: 2rem; font-weight: bold;">${dados.totais.bolsas}</p>
        </div>
        <div class="card" style="border-left: 5px solid var(--verde-forte);">
            <h3>⚡ Notícias</h3>
            <p style="font-size: 2rem; font-weight: bold;">${dados.totais.noticias}</p>
        </div>
        <div class="card" style="grid-column: 1 / -1;">
            <h3>📊 Distribuição de Categorias (PRAE)</h3>
            <div style="margin-top: 15px;">
                ${dados.prae_categorias.map(c => `
                    <div style="margin-bottom: 10px;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>${c.categoria}</span>
                            <span><b>${c.total}</b></span>
                        </div>
                        <div style="background: #eee; height: 8px; border-radius: 4px;">
                            <div style="background: var(--laranja); height: 100%; width: ${(c.total / 10) * 100}%; border-radius: 4px;"></div>
                        </div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

// 3. NOVA FUNÇÃO: MongoDB Inspector
async function carregarInspector() {
    const container = document.getElementById('container-vagas');
    container.style.display = 'block';
    container.innerHTML = '<p class="carregando">Lendo metadados físicos...</p>';

    document.querySelectorAll('.controles button').forEach(b => b.classList.remove('ativo'));
    document.getElementById('btn-inspector').classList.add('ativo');

    const res = await fetch(`${API_URL}/db-status`);
    const info = await res.json();

    container.innerHTML = `
        <div class="card" style="grid-column: 1/-1;">
            <h3>🛡️ MongoDB Inspector</h3>
            <pre>${JSON.stringify(info, null, 2)}</pre>
        </div>
    `;
}

function renderizarCards(listaDeVagas) {
    const container = document.getElementById('container-vagas');
    container.innerHTML = ''; 

    if (listaDeVagas.length === 0) {
        container.innerHTML = '<p class="carregando">Nenhuma oportunidade encontrada.</p>';
        return;
    }

    listaDeVagas.forEach(vaga => {
        const temaVerde = vaga.categoria === "Notícia Tech" ? "card-verde" : "";
        const cardHTML = `
            <div class="card ${temaVerde}">
                <div>
                    <span class="card-categoria">${vaga.categoria || 'Geral'}</span>
                    <h3 class="card-titulo">${vaga.nome}</h3>
                    <p class="card-fonte">Fonte: ${vaga.fonte}</p>
                </div>
                <a href="${vaga.link}" target="_blank" class="card-link">Acessar</a>
            </div>
        `;
        container.innerHTML += cardHTML;
    });
}

// Função que aciona o Botão Vermelho
async function acionarTodosOsRobos() {
    const container = document.getElementById('container-vagas');
    const btn = document.getElementById('btn-buscar-tudo');
    
    btn.innerText = "⏳ Raspando...";
    btn.disabled = true;
    
    container.innerHTML = '<div style="text-align: center; padding: 40px;"><h2>Protocolo Iniciado...</h2></div>';
    
    try {
        await fetch(`${API_URL}/buscar-tudo`);
        btn.innerText = "Buscar 🤖";
        btn.disabled = false;
        carregarDados('estagios');
    } catch (erro) {
        container.innerHTML = '<p class="carregando" style="color: red;">Erro ao rodar robôs.</p>';
        btn.innerText = "Erro!";
        btn.disabled = false;
    }
}