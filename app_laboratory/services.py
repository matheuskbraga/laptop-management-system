"""Regras de negócio compartilhadas entre views e formulários."""
from .models import Agendamento, Notebook


def frota_operacional():
    """Notebooks que podem ser usados (tudo o que não está quebrado)."""
    return Notebook.objects.exclude(status=Notebook.Status.QUEBRADO).count()


def pico_reservado(agendamentos, inicio, fim):
    """Maior quantidade reservada simultaneamente dentro da janela [inicio, fim).

    Duas reservas que não se sobrepõem entre si (ex.: 8h-10h e 10h-12h) não
    somam, por isso fazemos uma varredura nos instantes de início.
    """
    sobrepostos = [a for a in agendamentos if a.hora_inicio < fim and a.hora_fim > inicio]
    if not sobrepostos:
        return 0
    instantes = {inicio} | {a.hora_inicio for a in sobrepostos if a.hora_inicio > inicio}
    return max(
        sum(a.quantidade for a in sobrepostos if a.hora_inicio <= t < a.hora_fim)
        for t in instantes
    )


def agendamentos_confirmados(data, excluir=None):
    qs = Agendamento.objects.filter(data=data, status=Agendamento.Status.CONFIRMADO)
    if excluir is not None:
        qs = qs.exclude(pk=excluir.pk)
    return list(qs)


def capacidade_livre(data, inicio, fim, excluir=None):
    """Quantos notebooks ainda podem ser reservados nesse dia/horário."""
    reservado = pico_reservado(agendamentos_confirmados(data, excluir), inicio, fim)
    return max(frota_operacional() - reservado, 0)
