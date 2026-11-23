
"""Testes dos endpoints: a aplicação inteira, atravessada por HTTP.

Os arquivos anteriores chamam funções e métodos diretamente. Este faz
**requisições**: chega pela rota, passa pelo serviço, pelo repositório e pelo
modelo, e volta como JSON. É o nível que prova que as camadas conversam.

| | Teste de domínio | Teste de API |
|---|---|---|
| O que prova | que a regra está certa | que a regra chega ao cliente |
| Quando falha | diz exatamente qual regra | diz que algo no caminho quebrou |
| Custo | microssegundos | milissegundos |

Nenhum dos dois substitui o outro.
"""
from datetime import date, timedelta
from fastapi.testclient import TestClient


#: Corpo de cadastro válido, reaproveitado com `{**USUARIO_VALIDO, "campo": ...}`.
#:
#: É o mesmo papel das fábricas `nova_tarefa` e `novo_usuario` do Dia 1: um
#: ponto único a alterar quando o contrato de entrada mudar.
USUARIO_VALIDO = {
    "nome": "Bruno Lima",
    "email": "bruno@exemplo.com",
    "senha": "senha123",
}


# =============================================================================
# Dia 7 — `TestClient`: os endpoints públicos
# =============================================================================

def test_raiz_responde(cliente: TestClient):
    """O teste mais simples do arquivo, e o que falha primeiro quando a
    aplicação nem sobe. Serve de *smoke test*: se este falha, não vale
    investigar os outros."""
    assert cliente.get("/").status_code == 200


def test_cadastrar_usuario_devolve_201_com_sessao_aberta(cliente: TestClient):
    """O cadastro já devolve o token: quem criou a conta está autenticado.

    Três coisas são verificadas de uma vez, e cada uma é parte do contrato: o
    **código** 201 (recurso criado), o **corpo** com o token, e o **formato**
    dos nomes de campo — `criadoEm`, em camelCase, e não `criado_em`.
    """
    resposta = cliente.post("/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["accessToken"]
    assert corpo["tokenType"] == "bearer"
    assert corpo["usuario"]["nome"] == "Bruno Lima"
    assert "criadoEm" in corpo["usuario"], "o contrato usa camelCase"

def test_cadastro_nao_expoe_a_senha(cliente: TestClient):
    """Nem a senha nem o hash dela podem aparecer na resposta (RN-05).

    A verificação é feita sobre `resposta.text` — o JSON como texto, antes de
    ser interpretado — de propósito: assim ela não depende de saber em qual
    campo o vazamento aconteceria.

    As duas grafias são procuradas porque a API traduz nomes na borda: o que no
    Python se chama `senha_hash` chegaria ao cliente como `senhaHash`.
    """
    resposta = cliente.post("/usuarios", json=USUARIO_VALIDO)
    inteiro = resposta.text
    assert "senha123" not in inteiro
    assert "senhaHash" not in inteiro and "senha_hash" not in inteiro
    
def test_cadastrar_com_email_repetido_devolve_409(cliente: TestClient):
    """409 Conflict: o pedido está correto, o estado atual é que não permite."""
    cliente.post("/usuarios", json=USUARIO_VALIDO)
    resposta = cliente.post("/usuarios", json=USUARIO_VALIDO)
    assert resposta.status_code == 409
    assert resposta.json()["detail"] == "E-mail já cadastrado."


def test_email_duplicado_ignora_maiusculas_e_espacos(cliente: TestClient):
    """RN-01 de verdade: o mesmo endereço escrito de outra forma é duplicata."""
    cliente.post("/usuarios", json=USUARIO_VALIDO)
    resposta = cliente.post(
        "/usuarios", json={**USUARIO_VALIDO, "email": " BRUNO@Exemplo.com "}
    )
    assert resposta.status_code == 409


def test_email_malformado_devolve_422(cliente: TestClient):
    """422 vem do Pydantic, antes de a requisição chegar ao serviço."""
    resposta = cliente.post("/usuarios", json={**USUARIO_VALIDO, "email": "bruno@"})
    assert resposta.status_code == 422


def test_senha_curta_devolve_422(cliente: TestClient):
    resposta = cliente.post("/usuarios", json={**USUARIO_VALIDO, "senha": "123"})
    assert resposta.status_code == 422


def test_login_correto_devolve_200_com_token(cliente: TestClient, usuario: dict):
    """200 e não 201: o login não cria recurso nenhum, só abre sessão.

    O usuário já existe porque o teste pediu a fixture `usuario`, que faz o
    cadastro antes do teste começar.
    """
    resposta = cliente.post(
        "/usuarios/login", json={"email": "ana@exemplo.com", "senha": "senha123"}
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["usuario"]["id"] == usuario["id"]
    assert corpo["accessToken"]


def test_login_com_senha_errada_devolve_401(cliente: TestClient, usuario: dict):
    resposta = cliente.post(
        "/usuarios/login", json={"email": "ana@exemplo.com", "senha": "errada"}
    )
    assert resposta.status_code == 401


def test_login_com_email_inexistente_devolve_401_com_a_mesma_mensagem(
    cliente: TestClient, usuario: dict
):
    """Mensagem idêntica nos dois casos: não revela quais e-mails existem.

    Repare no formato do teste: ele não verifica *qual* é a mensagem, e sim que
    as duas são **iguais**. É uma propriedade, não um valor.
    """
    inexistente = cliente.post(
        "/usuarios/login", json={"email": "ninguem@exemplo.com", "senha": "senha123"}
    )
    senha_errada = cliente.post(
        "/usuarios/login", json={"email": "ana@exemplo.com", "senha": "errada"}
    )
    assert inexistente.status_code == senha_errada.status_code == 401
    assert inexistente.json()["detail"] == senha_errada.json()["detail"]


def test_nao_existe_mais_busca_de_usuario_por_id(cliente: TestClient):
    """`GET /usuarios/{id}` saiu da API — era enumeração de contas.

    Um teste que verifica a **ausência** de um endpoint impede que a rota volte
    numa refatoração futura "porque o front-end precisava".
    """
    assert cliente.get("/usuarios/1").status_code == 404
    assert cliente.get("/usuarios/9999").status_code == 404


def test_consultar_a_propria_conta_exige_token(cliente: TestClient):
    """401 e não 403: o servidor não sabe quem está pedindo."""
    assert cliente.get("/usuarios/eu").status_code == 401


def test_openapi_expoe_os_sete_endpoints(cliente: TestClient):
    """A API documenta exatamente o que tem — nada a mais.

    Uma rota acrescentada sem intenção, ou uma que devia ter saído e ficou,
    muda este número.
    """
    caminhos = cliente.get("/openapi.json").json()["paths"]
    operacoes = sum(len(metodos) for metodos in caminhos.values())
    assert operacoes == 8, "7 endpoints da API + a rota raiz"

# =============================================================================
# Dia 8 — `cliente_logado`: as tarefas, com a sessão aberta
# =============================================================================
#
# Todos os endpoints de /tasks exigem token, e o dono da tarefa vem do token.
# Por isso estes testes usam `cliente_logado` — um cliente que já envia o
# cabeçalho `Authorization` — e os corpos não trazem `usuarioId`.


def test_consultar_a_propria_conta_devolve_o_usuario_do_token(
    cliente_logado: TestClient, usuario: dict
):
    """A comparação é com o dicionário **inteiro** (`== usuario`): um campo a
    mais ou a menos quebra o teste."""
    resposta = cliente_logado.get("/usuarios/eu")
    assert resposta.status_code == 200
    assert resposta.json() == usuario


def test_criar_tarefa_nasce_pendente(cliente_logado: TestClient, usuario: dict):
    """A RN-02 do Dia 1, agora verificada do outro lado da aplicação.
    Entre o objeto `Tarefa` e esta resposta há uma rota, um schema de entrada,
    um serviço, um repositório e uma gravação no banco.
    """
    resposta = cliente_logado.post(
        "/tasks",
        json={
            "titulo": "Entregar o relatório",
            "prioridade": "alta",
            "prazo": str(date.today() + timedelta(days=30)),
        },
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["status"] == "pendente"
    assert corpo["concluidoEm"] is None
    assert corpo["usuarioId"] == usuario["id"], "o dono vem do token"


def test_criar_tarefa_sem_token_devolve_401(cliente: TestClient):
    """Usa `cliente`, e não `cliente_logado`: a ausência do token é o cenário."""
    assert cliente.post("/tasks", json={"titulo": "X"}).status_code == 401


def test_criar_tarefa_com_prioridade_invalida_devolve_422(
    cliente_logado: TestClient,
):
    resposta = cliente_logado.post(
        "/tasks", json={"titulo": "X", "prioridade": "altissima"}
    )
    assert resposta.status_code == 422

def test_listar_tarefas_de_usuario_sem_tarefas_devolve_lista_vazia(
    cliente_logado: TestClient,
):
    """Lista vazia é 200, não 404: a coleção existe, só está vazia."""
    resposta = cliente_logado.get("/tasks")
    assert resposta.status_code == 200
    assert resposta.json() == []


def test_listar_filtra_por_status(cliente_logado: TestClient):
    """O estado do teste é montado pela própria API, não pelo banco.
    Para ter uma tarefa concluída, o teste cria duas pela API e conclui uma
    pela API. Nenhuma linha de SQL, nenhuma sessão.
    """
    for titulo in ("A", "B"):
        cliente_logado.post("/tasks", json={"titulo": titulo})
    primeira = cliente_logado.get("/tasks").json()[0]
    cliente_logado.patch(f"/tasks/{primeira['id']}", json={"status": "concluida"})
    pendentes = cliente_logado.get("/tasks?status=pendente").json()
    assert len(pendentes) == 1
    assert pendentes[0]["status"] == "pendente"


def test_listar_ordena_por_prioridade_da_mais_urgente_para_a_menos(
    cliente_logado: TestClient,
):
    """A asserção compara a **lista inteira**, na ordem."""
    for prioridade in ("baixa", "urgente", "media"):
        cliente_logado.post(
            "/tasks", json={"titulo": prioridade, "prioridade": prioridade}
        )
    resposta = cliente_logado.get("/tasks?ordenarPor=prioridade&ordem=asc")
    assert [t["prioridade"] for t in resposta.json()] == [
        "urgente",
        "media",
        "baixa",
    ]


def test_campo_de_ordenacao_invalido_devolve_422(cliente_logado: TestClient):
    """Recusar é melhor que adivinhar: o erro aparece em quem o cometeu."""
    resposta = cliente_logado.get("/tasks?ordenarPor=inventado")
    assert resposta.status_code == 422


def test_filtrar_por_prazo_ate(cliente_logado: TestClient):
    """Datas relativas a hoje, e não fixas no calendário.
    Um teste que quebra pela passagem do tempo é pior do que não ter o teste:
    falha sem que ninguém tenha mexido em nada.
    """
    hoje = date.today()
    cliente_logado.post(
        "/tasks",
        json={"titulo": "Vence logo", "prazo": str(hoje + timedelta(days=1))},
    )
    cliente_logado.post(
        "/tasks",
        json={"titulo": "Vence tarde", "prazo": str(hoje + timedelta(days=30))},
    )
    resposta = cliente_logado.get(
        f"/tasks?prazoAte={hoje + timedelta(days=7)}"
    )
    assert [t["titulo"] for t in resposta.json()] == ["Vence logo"]
    
def test_concluir_tarefa_preenche_a_data(cliente_logado: TestClient):
    criada = cliente_logado.post("/tasks", json={"titulo": "Concluir"}).json()
    resposta = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"status": "concluida"}
    )
    assert resposta.status_code == 200
    assert resposta.json()["concluidoEm"] is not None


def test_reabrir_tarefa_limpa_a_data(cliente_logado: TestClient):
    criada = cliente_logado.post("/tasks", json={"titulo": "Reabrir"}).json()
    cliente_logado.patch(f"/tasks/{criada['id']}", json={"status": "concluida"})
    resposta = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"status": "pendente"}
    )
    assert resposta.json()["concluidoEm"] is None


def test_editar_titulo_de_tarefa_concluida_preserva_a_data(
    cliente_logado: TestClient,
):
    """A RN-03 verificada de ponta a ponta, atravessando todas as camadas.
    É a mesma regra do Dia 2, vista pelo outro lado. Se ela quebrar, compare
    as duas mensagens de falha: a do domínio aponta o método; esta diz apenas
    que duas datas vindas de duas respostas HTTP não são iguais.
    """
    criada = cliente_logado.post("/tasks", json={"titulo": "Original"}).json()
    concluida = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"status": "concluida"}
    ).json()
    editada = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"titulo": "Título novo"}
    ).json()
    assert editada["titulo"] == "Título novo"
    assert editada["concluidoEm"] == concluida["concluidoEm"]


def test_apagar_o_prazo_e_diferente_de_nao_informar(cliente_logado: TestClient):
    """No JSON, "não mencionei o prazo" e "quero o prazo vazio" são coisas
    diferentes: a primeira é a ausência da chave, a segunda é `null`."""
    prazo = str(date.today() + timedelta(days=10))
    criada = cliente_logado.post(
        "/tasks", json={"titulo": "Com prazo", "prazo": prazo}
    ).json()
    sem_mencionar = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"titulo": "Outro título"}
    ).json()
    assert sem_mencionar["prazo"] == prazo
    apagando = cliente_logado.patch(
        f"/tasks/{criada['id']}", json={"prazo": None}
    ).json()
    assert apagando["prazo"] is None


def test_atualizar_tarefa_inexistente_devolve_404(cliente_logado: TestClient):
    resposta = cliente_logado.patch("/tasks/9999", json={"status": "concluida"})
    assert resposta.status_code == 404


def test_titulo_vazio_no_patch_devolve_422(cliente_logado: TestClient):
    criada = cliente_logado.post("/tasks", json={"titulo": "Original"}).json()
    resposta = cliente_logado.patch(f"/tasks/{criada['id']}", json={"titulo": " "})
    assert resposta.status_code == 422

def test_remover_tarefa_devolve_204_sem_corpo(cliente_logado: TestClient):
    """204 No Content: o corpo precisa estar **vazio**, não só ausente."""
    criada = cliente_logado.post("/tasks", json={"titulo": "Remover"}).json()
    resposta = cliente_logado.delete(f"/tasks/{criada['id']}")
    assert resposta.status_code == 204
    assert resposta.content == b""


def test_remover_a_mesma_tarefa_duas_vezes_devolve_404(cliente_logado: TestClient):
    """A segunda remoção não é sucesso silencioso: a tarefa não existe mais."""
    criada = cliente_logado.post("/tasks", json={"titulo": "Remover"}).json()
    cliente_logado.delete(f"/tasks/{criada['id']}")
    assert cliente_logado.delete(f"/tasks/{criada['id']}").status_code == 404

