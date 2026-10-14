"""Popula o banco com dados fictícios para testar o visual localmente.

Uso:  python manage.py popular_demo
Não use em produção: o comando recusa rodar se já existirem notebooks (use --forcar).
"""
import random
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from app_laboratory.models import Agendamento, Baixa, Emprestimo, Notebook

PESSOAS = ['Ana Souza', 'Bruno Lima', 'Carla Mendes', 'Diego Rocha', 'Elisa Prado', 'Felipe Nunes',
           'Gabriela Reis', 'Henrique Alves', 'Isabela Costa', 'João Pedro']
MODELOS = ['Dell Latitude 3420', 'Lenovo ThinkPad E14', 'Positivo Master N', 'Acer Aspire 5']


class Command(BaseCommand):
    help = 'Cria notebooks, empréstimos, baixas e agendamentos de exemplo.'

    def add_arguments(self, parser):
        parser.add_argument('--forcar', action='store_true', help='Roda mesmo se já houver notebooks.')

    def handle(self, *args, forcar=False, **opts):
        if Notebook.objects.exists() and not forcar:
            raise CommandError('Já existem notebooks cadastrados. Use --forcar se tiver certeza.')
        random.seed(42)
        usuario = get_user_model().objects.order_by('pk').first()
        agora = timezone.now()
        hoje = timezone.localdate()

        nbs = []
        for n in range(1, 31):
            nb, _ = Notebook.objects.get_or_create(numero=f'NB-{n:02d}', defaults={'modelo': random.choice(MODELOS)})
            nbs.append(nb)

        # histórico já devolvido
        for nb in random.sample(nbs, 14):
            saida = agora - timedelta(days=random.randint(2, 20), hours=random.randint(0, 6))
            Emprestimo.objects.create(
                notebook=nb, pessoa=random.choice(PESSOAS), finalidade='Aula prática',
                retirado_em=saida, devolvido_em=saida + timedelta(hours=random.randint(2, 30)),
                registrado_por=usuario, recebido_por=usuario,
            )

        # empréstimos em andamento (dois atrasados)
        for i, nb in enumerate(nbs[3:11]):
            prevista = agora + timedelta(hours=random.randint(2, 48)) if i > 1 else agora - timedelta(hours=5 + i)
            Emprestimo.objects.create(
                notebook=nb, pessoa=PESSOAS[i], contato=f'Turma {i + 1}º ano', finalidade='Projeto de pesquisa',
                retirado_em=agora - timedelta(hours=random.randint(1, 30)), devolucao_prevista=prevista,
                registrado_por=usuario,
            )
            nb.status = Notebook.Status.EMPRESTADO
            nb.save()

        # quebrados
        for nb, motivo in [(nbs[13], 'Tela trincada no canto inferior direito.'),
                           (nbs[21], 'Não liga. Possível problema na fonte/carregador.')]:
            Baixa.objects.create(notebook=nb, motivo=motivo, registrado_por=usuario,
                                 registrado_em=agora - timedelta(days=random.randint(1, 5)))
            nb.status = Notebook.Status.QUEBRADO
            nb.save()

        # agenda
        exemplos = [
            (0, 'Aula de robótica', Agendamento.Tipo.AULA, time(8), time(10), 12),
            (0, 'Oficina de planilhas', Agendamento.Tipo.FORMACAO, time(14), time(16), 8),
            (1, 'Formação de professores', Agendamento.Tipo.FORMACAO, time(9), time(12), 20),
            (2, 'Feira de ciências: preparação', Agendamento.Tipo.PROJETO, time(13), time(17), 10),
            (4, 'Simulado online', Agendamento.Tipo.TAREFA, time(7, 30), time(11, 30), 25),
            (6, 'Hackathon interno', Agendamento.Tipo.EVENTO, time(8), time(18), 15),
            (9, 'Aula de programação', Agendamento.Tipo.AULA, time(10), time(12), 18),
            (13, 'Projeto de jornal escolar', Agendamento.Tipo.PROJETO, time(14), time(16), 6),
        ]
        for dias, titulo, tipo, ini, fim, qtd in exemplos:
            Agendamento.objects.create(
                titulo=titulo, tipo=tipo, data=hoje + timedelta(days=dias), hora_inicio=ini, hora_fim=fim,
                quantidade=qtd, solicitante=random.choice(PESSOAS), criado_por=usuario,
            )

        self.stdout.write(self.style.SUCCESS('Dados de demonstração criados.'))
