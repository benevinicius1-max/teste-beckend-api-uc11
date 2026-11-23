
"""Configuração comum dos testes.

O pytest encontra este arquivo automaticamente e aplica as fixtures
compartilhadas a todos os testes da pasta.
"""

import os

# As variáveis de ambiente devem ser definidas antes de importar a aplicação.
# O banco SQLite em memória evita alterar o banco real do projeto.
os.environ["DATABASE_URL"] = "sqlite://"

# Segredo utilizado exclusivamente durante os testes.
os.environ["JWT_SECRET"] = "segredo-de-teste-nao-usar-em-producao"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database import Base, SessionLocal, criar_tabelas, engine  # noqa: E402
from app.dependencies import obter_hasher  # noqa: E402
from app.main import app  # noqa: E402
from app.security import HashBcrypt, HashDeSenha  # noqa: E402


# =============================================================================
# Dia 4 — A primeira fixture compartilhada
# =============================================================================

@pytest.fixture
def hasher() -> HashBcrypt:
    """O hash de senha verdadeiro, com o custo mínimo para os testes.

    O custo 4 é o mínimo aceito pelo bcrypt e permite executar
    os testes rapidamente, sem alterar o comportamento verificado.
    """
    return HashBcrypt(custo=4)


# =============================================================================
# Dia 5 — O banco: limpo antes, limpo depois
# =============================================================================

@pytest.fixture(autouse=True)
def banco_limpo():
    """Garante um banco vazio antes e depois de cada teste.

    A fixture é executada automaticamente em todos os testes.
    """
    Base.metadata.drop_all(bind=engine)
    criar_tabelas()

    yield

    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sessao() -> Session:
    """Sessão de banco para testes que precisam gravar diretamente.

    O rollback desfaz transações pendentes e o close encerra a sessão.
    """
    sessao = SessionLocal()

    try:
        yield sessao
    finally:
        sessao.rollback()
        sessao.close()


# =============================================================================
# Dia 7 — HTTP: o dublê e o cliente
# =============================================================================

class HashFake(HashDeSenha):
    """Hash previsível e instantâneo, exclusivo dos testes de API.

    Substitui o bcrypt nos testes HTTP para evitar o custo de processamento.

    O formato fake$senha permite identificar facilmente os valores
    utilizados durante os testes.

    Esta implementação nunca deve ser utilizada em produção.
    """

    def gerar(self, senha: str) -> str:
        return f"fake${senha}"

    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        return hash_armazenado == self.gerar(senha)


@pytest.fixture
def cliente(banco_limpo) -> TestClient:
    """Cliente HTTP sem autenticação, utilizando o HashFake.

    dependency_overrides substitui a implementação real do hash
    exclusivamente durante a execução dos testes HTTP.

    O finally remove as substituições para evitar interferências
    nos próximos testes.
    """
    app.dependency_overrides[obter_hasher] = HashFake

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# =============================================================================
# Dia 7 — Fixtures de usuário e sessão autenticada
# =============================================================================

@pytest.fixture
def sessao_aberta(cliente: TestClient) -> dict:
    """Cadastra um usuário e devolve o token e os dados da conta.

    A fixture cliente prepara automaticamente o banco e o HashFake.
    """
    resposta = cliente.post(
        "/usuarios",
        json={
            "nome": "Ana Souza",
            "email": "ana@exemplo.com",
            "senha": "senha123",
        },
    )

    assert resposta.status_code == 201, resposta.text

    return resposta.json()


@pytest.fixture
def usuario(sessao_aberta: dict) -> dict:
    """Devolve os dados do usuário cadastrado pela sessao_aberta."""
    return sessao_aberta["usuario"]

# =============================================================================
# Dia 7 — HTTP: o dublê e o cliente
# =============================================================================
class HashFake(HashDeSenha):
    """Hash previsível e instantâneo, para uso exclusivo nos testes de API.

    É um **dublê de teste**: um substituto que cumpre o mesmo contrato do objeto
    real e serve a um propósito diferente.

    Existe porque a aplicação usa o bcrypt com custo 12 — centenas de
    milissegundos por hash, de propósito, para encarecer um ataque de força
    bruta. Cada cadastro e cada login pela API pagariam esse custo, sem testar
    nada de novo.

    Só é possível substituir porque `HashDeSenha` é uma classe abstrata, e a
    aplicação depende do contrato, não da implementação.

    O formato `fake$senha` é legível de propósito: quando um teste falha, a
    mensagem mostra exatamente qual senha foi usada. Em produção isso seria uma
    falha grave de segurança — e é por isso que esta classe nunca sai de
    `tests/`. A resistência do algoritmo real continua verificada em
    `test_seguranca.py`.
    """

    def gerar(self, senha: str) -> str:
        return f"fake${senha}"

    def verificar(self, senha: str, hash_armazenado: str) -> bool:
        return hash_armazenado == self.gerar(senha)


@pytest.fixture
def cliente(banco_limpo) -> TestClient:
    """Cliente HTTP **sem** autenticação, com o hash substituído pelo dublê.

    **`dependency_overrides`** é o mecanismo do FastAPI para trocar uma
    dependência durante o teste. A aplicação pede `obter_hasher`; aqui o
    `HashFake` é posto no lugar, e o serviço nem sabe da substituição.

    O `finally` com `clear()` é obrigatório: `app` é um objeto global,
    compartilhado por todos os testes. Uma substituição que não fosse desfeita
    vazaria para o teste seguinte.

    **`TestClient(app)` é usado sem `with` de propósito.** Com `with`, o
    cliente dispara o ciclo de vida da aplicação, que tentaria criar as tabelas
    de novo. Quem cuida disso é a `banco_limpo`, pedida aqui no parâmetro para
    garantir a ordem: banco limpo primeiro, cliente depois.
    """
    app.dependency_overrides[obter_hasher] = HashFake

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sessao_aberta(cliente: TestClient) -> dict:
    """Cadastra um usuário e devolve a resposta do cadastro: token e usuário.

    Uma fixture que **pede outra**: ela recebe o `cliente` pronto.

    O `assert` aqui dentro não é um teste: é uma **pré-condição**. Se o
    cadastro falhar, o erro aparece aqui, com o corpo da resposta na mensagem,
    em vez de virar um `KeyError` incompreensível dentro do teste.
    """
    resposta = cliente.post(
        "/usuarios",
        json={"nome": "Ana Souza", "email": "ana@exemplo.com", "senha": "senha123"},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


@pytest.fixture
def usuario(sessao_aberta: dict) -> dict:
    """Um usuário já cadastrado: o dicionário `usuario` da resposta.

    A cadeia inteira — `banco_limpo` → `cliente` → `sessao_aberta` →
    `usuario` — é montada pelo pytest na ordem certa. Um teste que pede só
    `usuario` recebe tudo isso de graça.
    """
    return sessao_aberta["usuario"]

# =============================================================================
# Dia 8 — a sessão aberta
# =============================================================================

@pytest.fixture
def token(sessao_aberta: dict) -> str:
    """O token de acesso do usuário da fixture `usuario`.

    `usuario` e `token` pedem a **mesma** `sessao_aberta`. O pytest cria cada
    fixture uma única vez por teste, então os dois vêm do mesmo cadastro — o
    token identifica exatamente aquele usuário, e não um segundo parecido.
    """
    return sessao_aberta["accessToken"]


@pytest.fixture
def cliente_logado(cliente: TestClient, token: str) -> TestClient:
    """Cliente HTTP que envia `Authorization: Bearer <token>` em toda chamada.

    O cabeçalho entra nos *headers* padrão do cliente em vez de ser repetido em
    cada requisição: o que cada teste verifica é o comportamento do endpoint,
    não a montagem do cabeçalho — essa é verificada à parte, em
    `test_autenticacao.py`.
    """
    cliente.headers["Authorization"] = f"Bearer {token}"
    return cliente

# =============================================================================
# Dia 9 — a segunda conta
# =============================================================================

@pytest.fixture
def outro_usuario(cliente: TestClient) -> dict:
    """Uma segunda conta, com a sua própria sessão.
    Provar que uma conta não alcança as tarefas da outra exige duas contas de
    verdade. Devolve a resposta inteira do cadastro — token e usuário —,
    porque os testes de isolamento precisam dos dois.
    """
    resposta = cliente.post(
        "/usuarios",
        json={"nome": "Bruno Lima", "email": "bruno@exemplo.com", "senha": "senha456"},
    )
    assert resposta.status_code == 201, resposta.text
    return resposta.json()