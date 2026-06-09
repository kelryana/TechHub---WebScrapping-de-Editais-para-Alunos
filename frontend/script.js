// URL base da sua API FastAPI
const API_URL = "http://localhost:8000/api";

// Função principal que busca os dados
async function carregarDados(tipo) {
    const container = document.getElementById('container-vagas');
    container.innerHTML = '<p class="carregando">Buscando dados no banco...</p>';

    // JEITO NOVO E ESCALÁVEL: Remove a classe 'ativo' de TODOS os botões de uma vez
    document.querySelectorAll('.controles button').forEach(botao => {
        botao.classList.remove('ativo');
    });
    // Adiciona a classe 'ativo' só no botão que foi clicado
    document.getElementById(`btn-${tipo}`).classList.add('ativo');

    try {
        // ... (o resto do código fetch continua igualzinho!)
        const resposta = await fetch(`${API_URL}/${tipo}`);
        const dados = await resposta.json();

        renderizarCards(dados);
    } catch (erro) {
        console.error("Erro ao buscar dados:", erro);
        container.innerHTML = '<p class="carregando" style="color: red;">Erro ao conectar com a API. O FastAPI está rodando?</p>';
    }
}

// Função que desenha o HTML na tela baseado nos dados
function renderizarCards(listaDeVagas) {
    const container = document.getElementById('container-vagas');
    container.innerHTML = ''; 

    if (listaDeVagas.length === 0) {
        container.innerHTML = '<p class="carregando">Nenhuma oportunidade encontrada no banco.</p>';
        return;
    }

    listaDeVagas.forEach(vaga => {
        // Verifica se é notícia para aplicar o tema verde
        const temaVerde = vaga.categoria === "Notícia Tech" ? "card-verde" : "";

        // Adicionamos a variável temaVerde na classe principal do card
        const cardHTML = `
            <div class="card ${temaVerde}">
                <div>
                    <span class="card-categoria">${vaga.categoria}</span>
                    <h3 class="card-titulo">${vaga.nome}</h3>
                    <p class="card-fonte">Fonte: ${vaga.fonte}</p>
                </div>
                <a href="${vaga.link}" target="_blank" class="card-link">Acessar</a>
            </div>
        `;
        
        container.innerHTML += cardHTML;
    });
}

// Quando a página carregar, puxa os estágios por padrão
window.onload = () => {
    carregarDados('estagios');
};

// Função que aciona o Botão Vermelho
async function acionarTodosOsRobos() {
    const container = document.getElementById('container-vagas');
    const btn = document.getElementById('btn-buscar-tudo');
    
    // 1. Efeito Visual: Botão fica Laranja e bloqueado
    btn.innerText = "⏳ Raspando a Web...";
    btn.disabled = true;
    
    // Tira a seleção dos botões azuis
    document.querySelectorAll('.controles button').forEach(b => b.classList.remove('ativo'));
    
    // 2. Mensagem Dramática na tela
    container.innerHTML = `
        <div style="text-align: center; grid-column: 1 / -1; padding: 40px;">
            <h2 style="color: #DC143C; margin-bottom: 20px; font-size: 2rem;">Iniciando Protocolo de Varredura...</h2>
            <p style="font-size: 1.2rem; color: #09184D;">O robô está limpando o banco de dados e acessando a PRAE, PROEX, UFERSA, CIEE e Portais de Notícias.</p>
            <p style="font-size: 1.2rem; margin-top: 15px;"><b>Atenção:</b> O navegador do CIEE vai abrir em instantes. Prepare-se para interagir!</p>
        </div>
    `;
    
    try {
        // 3. Faz a requisição para o back-end (Aqui ele vai ficar esperando os scripts terminarem)
        await fetch(`${API_URL}/buscar-tudo`);
        
        // 4. Quando terminar, volta o botão ao normal
        btn.innerText = "Buscar 🤖";
        btn.disabled = false;
        
        // 5. Aciona a aba de Estágios automaticamente para mostrar o resultado!
        carregarDados('estagios');
        
    } catch (erro) {
        container.innerHTML = '<p class="carregando" style="color: red;">Erro ao executar os robôs. O Back-end está rodando?</p>';
        btn.innerText = "Erro!";
        btn.disabled = false;
    }
}