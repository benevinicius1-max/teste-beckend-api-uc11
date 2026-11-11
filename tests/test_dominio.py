from app.enums import PrioridadeTarefa, StatusTarefa
from app.models import Tarefa, Usuario
from datetime import date, timedelta

def test_tarefa_nasce_pendente_e_sem_data_de_conclusao():
 """RN-02: toda tarefa nasce pendente."""
 tarefa = Tarefa(usuario_id=1, titulo="Estudar orientação a objetos")
 assert tarefa.status is StatusTarefa.PENDENTE
 assert tarefa.concluido_em is None
 
from app.enums import PrioridadeTarefa, StatusTarefa
from app.models import Tarefa, Usuario
def nova_tarefa(**ajustes) -> Tarefa:
 """Cria uma tarefa válida, permitindo sobrescrever campos pontualmente.
 Esta função não é um teste — é uma **fábrica**.
 """
 dados = {"usuario_id": 1, "titulo": "Estudar orientação a objetos"}
 dados.update(ajustes)
 return Tarefa(**dados)
def novo_usuario(**ajustes) -> Usuario:
 """Cria um usuário válido, permitindo sobrescrever campos pontualmente."""
 dados = {"nome": "Ana Souza", "email": "ana@exemplo.com"}
 dados.update(ajustes)
 return Usuario(**dados)
# =============================================================================
# Dia 1 — `assert`: o que o objeto faz
# =============================================================================
def test_tarefa_nasce_pendente_e_sem_data_de_conclusao():
 """RN-02: toda tarefa nasce pendente."""
 tarefa = nova_tarefa()
 assert tarefa.status is StatusTarefa.PENDENTE
 assert tarefa.concluido_em is None
def test_titulo_e_gravado_sem_espaços_nas_pontas():
    assert nova_tarefa(titulo="  Revisar  ").titulo == "Revisar"

def test_prioridade_aceita_enum_e_texto():
    assert nova_tarefa(prioridade=PrioridadeTarefa.ALTA).prioridade == "alta"
    assert nova_tarefa(prioridade="urgente").prioridade == "urgente"
def test_tarefa_sem_prazo_nunca_esta_atrasada():
 assert nova_tarefa(prazo=None).esta_atrasada() is False
def test_tarefa_com_prazo_vencido_e_pendente_esta_atrasada():
 ontem = date.today() - timedelta(days=1)
 assert nova_tarefa(prazo=ontem).esta_atrasada() is True
def test_pertence_a():
 tarefa = nova_tarefa(usuario_id=7)
 assert tarefa.pertence_a(7) is True
 assert tarefa.pertence_a(8) is False
def test_ordem_das_prioridades_vai_da_mais_urgente_para_a_menos():
 """Ordenar pelo texto daria "alta, baixa, media, urgente".
 O peso existe para que a ordenação siga o que o usuário espera, e não o
 alfabeto. Este teste trava essa expectativa.
 """
 pesos = [p.peso for p in (
 PrioridadeTarefa.URGENTE,
 PrioridadeTarefa.ALTA,
 PrioridadeTarefa.MEDIA,
 PrioridadeTarefa.BAIXA,
 )]
 assert pesos == sorted(pesos)
 
def test_email_e_normalizado_na_criacao():
    """RN-01: o e-mail é guardado sempre na mesama forma."""
    assert novo_usuario(email=" ANA@Exemplo.com").email == "ana@exemplo.com"
    

def test_nome_e_gravado_sem_espacos_nas_pontas():
    assert novo_usuario(nome="  Ana Souza  ").nome == "Ana Souza"
