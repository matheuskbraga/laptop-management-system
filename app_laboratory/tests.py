from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from .models import Agendamento, Baixa, Emprestimo, Notebook
from .services import capacidade_livre, pico_reservado


class BaseTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('gestor', password='senha-forte-123')
        self.client.force_login(self.user)
        self.nbs = [Notebook.objects.create(numero=f'NB-{i:02d}') for i in range(1, 6)]


class PaginasTest(BaseTest):
    def test_paginas_carregam(self):
        ag = Agendamento.objects.create(
            titulo='Aula', solicitante='Ana', data=timezone.localdate(),
            hora_inicio=time(8), hora_fim=time(10), quantidade=2,
        )
        for nome, args in [('painel', []), ('notebooks', []), ('notebook_novo', []),
                           ('notebook_detalhe', [self.nbs[0].pk]), ('emprestimos', []),
                           ('emprestimo_novo', []), ('agenda', []), ('agenda_novo', []),
                           ('agenda_detalhe', [ag.pk])]:
            with self.subTest(nome=nome):
                self.assertEqual(self.client.get(reverse(nome, args=args)).status_code, 200)

    def test_login_obrigatorio(self):
        self.client.logout()
        resp = self.client.get(reverse('painel'))
        self.assertRedirects(resp, f"{reverse('login')}?next=/")


class EmprestimoTest(BaseTest):
    def test_emprestimo_em_lote_e_devolucao(self):
        resp = self.client.post(reverse('emprestimo_novo'), {
            'notebooks': [self.nbs[0].pk, self.nbs[1].pk], 'pessoa': 'Carla',
        })
        self.assertRedirects(resp, reverse('emprestimos'))
        self.assertEqual(Notebook.objects.filter(status=Notebook.Status.EMPRESTADO).count(), 2)
        emp = Emprestimo.objects.get(notebook=self.nbs[0])
        self.assertEqual(emp.registrado_por, self.user)

        self.client.post(reverse('emprestimo_devolver', args=[emp.pk]))
        emp.refresh_from_db()
        self.nbs[0].refresh_from_db()
        self.assertIsNotNone(emp.devolvido_em)
        self.assertTrue(self.nbs[0].disponivel)

    def test_nao_empresta_notebook_quebrado(self):
        self.nbs[0].status = Notebook.Status.QUEBRADO
        self.nbs[0].save()
        resp = self.client.post(reverse('emprestimo_novo'), {'notebooks': [self.nbs[0].pk], 'pessoa': 'X'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Emprestimo.objects.exists())

    def test_atrasado(self):
        emp = Emprestimo.objects.create(
            notebook=self.nbs[0], pessoa='A', devolucao_prevista=timezone.now() - timedelta(hours=1)
        )
        self.assertTrue(emp.atrasado)


class BaixaTest(BaseTest):
    def test_baixa_exige_senha(self):
        nb = self.nbs[0]
        self.client.post(reverse('notebook_baixa', args=[nb.pk]), {'motivo': 'Tela', 'senha': 'errada'})
        nb.refresh_from_db()
        self.assertFalse(nb.quebrado)
        self.assertFalse(Baixa.objects.exists())

    def test_baixa_e_reparo(self):
        nb = self.nbs[0]
        Emprestimo.objects.create(notebook=nb, pessoa='Ana')
        nb.status = Notebook.Status.EMPRESTADO
        nb.save()

        self.client.post(reverse('notebook_baixa', args=[nb.pk]), {'motivo': 'Não liga', 'senha': 'senha-forte-123'})
        nb.refresh_from_db()
        self.assertTrue(nb.quebrado)
        self.assertEqual(nb.baixa_ativa.registrado_por, self.user)
        self.assertIsNone(nb.emprestimo_ativo, 'empréstimo deve ser encerrado na baixa')

        resp = self.client.get(reverse('notebooks'))
        self.assertContains(resp, 'nb quebrado')

        self.client.post(reverse('notebook_reparar', args=[nb.pk]), {'solucao': 'Trocou a fonte'})
        nb.refresh_from_db()
        self.assertTrue(nb.disponivel)
        self.assertEqual(Baixa.objects.get().solucao, 'Trocou a fonte')

    def test_remover_exige_post(self):
        resp = self.client.get(reverse('notebook_remover', args=[self.nbs[0].pk]))
        self.assertEqual(resp.status_code, 405)
        self.assertTrue(Notebook.objects.filter(pk=self.nbs[0].pk).exists())


class AgendaTest(BaseTest):
    def _ag(self, ini, fim, qtd, data=None):
        return Agendamento.objects.create(
            titulo='X', solicitante='Y', data=data or timezone.localdate() + timedelta(days=1),
            hora_inicio=time(ini), hora_fim=time(fim), quantidade=qtd,
        )

    def test_pico_considera_apenas_sobreposicao_real(self):
        a, b = self._ag(8, 10, 3), self._ag(10, 12, 4)
        self.assertEqual(pico_reservado([a, b], time(8), time(12)), 4)
        c = self._ag(9, 11, 1)
        self.assertEqual(pico_reservado([a, b, c], time(8), time(12)), 5)

    def test_capacidade_desconta_quebrados(self):
        amanha = timezone.localdate() + timedelta(days=1)
        self._ag(8, 10, 3)
        self.nbs[0].status = Notebook.Status.QUEBRADO
        self.nbs[0].save()
        self.assertEqual(capacidade_livre(amanha, time(9), time(11)), 1)

    def test_bloqueia_agendamento_acima_da_capacidade(self):
        self._ag(8, 10, 4)
        amanha = timezone.localdate() + timedelta(days=1)
        dados = {'titulo': 'Formação', 'tipo': 'formacao', 'solicitante': 'Rui', 'data': amanha.isoformat(),
                 'hora_inicio': '09:00', 'hora_fim': '11:00', 'quantidade': 2}
        resp = self.client.post(reverse('agenda_novo'), dados)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Só há 1 notebook')

        dados['quantidade'] = 1
        resp = self.client.post(reverse('agenda_novo'), dados)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Agendamento.objects.count(), 2)

    def test_retirada_pelo_agendamento(self):
        ag = self._ag(8, 10, 3, data=timezone.localdate())
        resp = self.client.get(reverse('emprestimo_novo') + f'?agendamento={ag.pk}')
        self.assertEqual(len(resp.context['form']['notebooks'].value()), 3)

    def test_disponibilidade_json(self):
        self._ag(8, 10, 2)
        amanha = (timezone.localdate() + timedelta(days=1)).isoformat()
        resp = self.client.get(reverse('agenda_disponibilidade'), {'data': amanha, 'inicio': '09:00', 'fim': '10:00'})
        self.assertEqual(resp.json()['livres'], 3)
        self.assertEqual(len(resp.json()['conflitos']), 1)


class MigracaoDadosTest(TransactionTestCase):
    """Garante que empréstimos da versão antiga viram registros de Emprestimo."""

    def test_migracao(self):
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        antigo = [('app_laboratory', '0002_rename_notebooks_notebook')]
        executor.migrate(antigo)
        velho = executor.loader.project_state(antigo).apps
        velho.get_model('app_laboratory', 'Notebook').objects.create(
            numero='OLD-1', esta_emprestado=True, pessoa_emprestada='Maria'
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

        nb = Notebook.objects.get(numero='OLD-1')
        self.assertTrue(nb.emprestado)
        self.assertEqual(nb.emprestimo_ativo.pessoa, 'Maria')
