import calendar
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AgendamentoForm, BaixaForm, EmprestimoForm, NotebookForm, NotebookLoteForm
from .models import Agendamento, Baixa, Emprestimo, Notebook
from .services import agendamentos_confirmados, capacidade_livre, frota_operacional, pico_reservado

MESES = [
    'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho',
    'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro',
]


def _voltar(request, padrao, *args):
    """Redireciona para ?next= (se for do próprio site) ou para a rota padrão."""
    destino = request.POST.get('next') or request.GET.get('next')
    if destino and url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        return redirect(destino)
    return redirect(padrao, *args)


def _notebooks_com_estado():
    return Notebook.objects.prefetch_related(
        Prefetch(
            'emprestimos',
            queryset=Emprestimo.objects.filter(devolvido_em__isnull=True),
            to_attr='_emprestimos_ativos',
        ),
        Prefetch('baixas', queryset=Baixa.objects.filter(resolvido_em__isnull=True), to_attr='_baixas_ativas'),
    )


def _atividade_recente(limite=12):
    eventos = []
    for e in Emprestimo.objects.select_related('notebook', 'registrado_por').order_by('-retirado_em')[:limite]:
        eventos.append({
            'quando': e.retirado_em, 'tipo': 'saida', 'usuario': e.registrado_por,
            'texto': f'{e.notebook} retirado por {e.pessoa}',
        })
    for e in (Emprestimo.objects.filter(devolvido_em__isnull=False)
              .select_related('notebook', 'recebido_por').order_by('-devolvido_em')[:limite]):
        eventos.append({
            'quando': e.devolvido_em, 'tipo': 'entrada', 'usuario': e.recebido_por,
            'texto': f'{e.notebook} devolvido por {e.pessoa}',
        })
    for b in Baixa.objects.select_related('notebook', 'registrado_por')[:limite]:
        eventos.append({
            'quando': b.registrado_em, 'tipo': 'baixa', 'usuario': b.registrado_por,
            'texto': f'{b.notebook} marcado como quebrado',
        })
    for b in (Baixa.objects.filter(resolvido_em__isnull=False)
              .select_related('notebook', 'resolvido_por').order_by('-resolvido_em')[:limite]):
        eventos.append({
            'quando': b.resolvido_em, 'tipo': 'reparo', 'usuario': b.resolvido_por,
            'texto': f'{b.notebook} voltou a funcionar',
        })
    for a in Agendamento.objects.select_related('criado_por').order_by('-criado_em')[:limite]:
        eventos.append({
            'quando': a.criado_em, 'tipo': 'agenda', 'usuario': a.criado_por,
            'texto': f'Agendado: {a.titulo} ({a.quantidade} un. em {a.data:%d/%m})',
        })
    eventos.sort(key=lambda ev: ev['quando'], reverse=True)
    return eventos[:limite]


# ---------------------------------------------------------------- painel

@login_required
def painel(request):
    contagem = Notebook.objects.aggregate(
        total=Count('id'),
        disponiveis=Count('id', filter=Q(status=Notebook.Status.DISPONIVEL)),
        emprestados=Count('id', filter=Q(status=Notebook.Status.EMPRESTADO)),
        quebrados=Count('id', filter=Q(status=Notebook.Status.QUEBRADO)),
    )
    operacionais = contagem['total'] - contagem['quebrados']
    contagem['uso_pct'] = round(100 * contagem['emprestados'] / operacionais) if operacionais else 0

    hoje = timezone.localdate()
    ativos = Emprestimo.objects.filter(devolvido_em__isnull=True).select_related('notebook')
    atrasados = [e for e in ativos if e.atrasado]

    return render(request, 'app_laboratory/painel.html', {
        'c': contagem,
        'atrasados': atrasados,
        'ativos': ativos[:8],
        'agenda_hoje': Agendamento.objects.filter(data=hoje, status=Agendamento.Status.CONFIRMADO)
                                          .annotate(retirados=Count('emprestimos')),
        'proximos': Agendamento.objects.filter(
            data__gt=hoje, data__lte=hoje + timedelta(days=7), status=Agendamento.Status.CONFIRMADO
        )[:6],
        'quebrados': _notebooks_com_estado().filter(status=Notebook.Status.QUEBRADO),
        'atividade': _atividade_recente(),
    })


# ---------------------------------------------------------------- notebooks

@login_required
def notebooks_lista(request):
    notebooks = _notebooks_com_estado()
    status = request.GET.get('status', '')
    if status in Notebook.Status.values:
        notebooks = notebooks.filter(status=status)
    q = request.GET.get('q', '').strip()
    if q:
        notebooks = notebooks.filter(
            Q(numero__icontains=q) | Q(modelo__icontains=q)
            | Q(emprestimos__pessoa__icontains=q, emprestimos__devolvido_em__isnull=True)
        ).distinct()

    contagem = Notebook.objects.aggregate(
        todos=Count('id'),
        disponivel=Count('id', filter=Q(status=Notebook.Status.DISPONIVEL)),
        emprestado=Count('id', filter=Q(status=Notebook.Status.EMPRESTADO)),
        quebrado=Count('id', filter=Q(status=Notebook.Status.QUEBRADO)),
    )
    return render(request, 'app_laboratory/notebooks.html', {
        'notebooks': notebooks, 'status': status, 'q': q, 'contagem': contagem,
        'baixa_form': BaixaForm(),
    })


@login_required
def notebook_novo(request):
    form, lote_form = NotebookForm(), NotebookLoteForm()
    modo = request.POST.get('modo', request.GET.get('modo', 'unico'))

    if request.method == 'POST' and modo == 'lote':
        lote_form = NotebookLoteForm(request.POST)
        if lote_form.is_valid():
            existentes = set(Notebook.objects.filter(numero__in=lote_form.numeros())
                             .values_list('numero', flat=True))
            novos = [Notebook(numero=n, modelo=lote_form.cleaned_data['modelo'])
                     for n in lote_form.numeros() if n not in existentes]
            Notebook.objects.bulk_create(novos)
            msg = f'{len(novos)} notebook(s) cadastrado(s).'
            if existentes:
                msg += f' {len(existentes)} já existiam e foram ignorados.'
            messages.success(request, msg)
            return redirect('notebooks')
    elif request.method == 'POST':
        form = NotebookForm(request.POST)
        if form.is_valid():
            nb = form.save()
            messages.success(request, f'Notebook {nb} cadastrado.')
            if 'outro' in request.POST:
                return redirect('notebook_novo')
            return redirect('notebooks')

    return render(request, 'app_laboratory/notebook_form.html', {
        'form': form, 'lote_form': lote_form, 'modo': modo,
    })


@login_required
def notebook_detalhe(request, pk):
    nb = get_object_or_404(_notebooks_com_estado(), pk=pk)
    return render(request, 'app_laboratory/notebook_detalhe.html', {
        'nb': nb,
        'emprestimos': nb.emprestimos.select_related('registrado_por', 'recebido_por', 'agendamento')[:50],
        'baixas': nb.baixas.select_related('registrado_por', 'resolvido_por'),
        'total_emprestimos': nb.emprestimos.count(),
        'baixa_form': BaixaForm(),
    })


@login_required
def notebook_editar(request, pk):
    nb = get_object_or_404(Notebook, pk=pk)
    form = NotebookForm(request.POST or None, instance=nb)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Notebook {nb} atualizado.')
        return redirect('notebook_detalhe', nb.pk)
    return render(request, 'app_laboratory/notebook_form.html', {'form': form, 'nb': nb, 'modo': 'unico'})


@login_required
@require_POST
def notebook_remover(request, pk):
    nb = get_object_or_404(Notebook, pk=pk)
    if nb.emprestado:
        messages.error(request, f'{nb} está emprestado. Registre a devolução antes de remover.')
        return _voltar(request, 'notebooks')
    nb.delete()
    messages.success(request, f'Notebook {nb} removido do inventário.')
    return redirect('notebooks')


@login_required
@require_POST
def notebook_baixa(request, pk):
    """Marca o notebook como quebrado. Exige a senha do gerenciador como autorização."""
    nb = get_object_or_404(Notebook, pk=pk)
    form = BaixaForm(request.POST, user=request.user)
    if nb.quebrado:
        messages.info(request, f'{nb} já está marcado como quebrado.')
    elif form.is_valid():
        with transaction.atomic():
            agora = timezone.now()
            # Se estava emprestado, o empréstimo é encerrado junto com a baixa
            for emp in nb.emprestimos.filter(devolvido_em__isnull=True):
                emp.devolvido_em = agora
                emp.recebido_por = request.user
                emp.observacoes = (emp.observacoes + '\n' if emp.observacoes else '') + \
                    'Encerrado automaticamente: notebook dado como quebrado.'
                emp.save()
            Baixa.objects.create(
                notebook=nb, motivo=form.cleaned_data['motivo'], registrado_por=request.user, registrado_em=agora
            )
            nb.status = Notebook.Status.QUEBRADO
            nb.save(update_fields=['status'])
        messages.warning(request, f'{nb} foi marcado como QUEBRADO e saiu de circulação.')
    else:
        erros = ' '.join(e for lista in form.errors.values() for e in lista)
        messages.error(request, f'Baixa de {nb} não realizada. {erros}')
    return _voltar(request, 'notebooks')


@login_required
@require_POST
def notebook_reparar(request, pk):
    nb = get_object_or_404(Notebook, pk=pk)
    if not nb.quebrado:
        return _voltar(request, 'notebooks')
    with transaction.atomic():
        nb.baixas.filter(resolvido_em__isnull=True).update(
            resolvido_em=timezone.now(), resolvido_por=request.user,
            solucao=request.POST.get('solucao', '').strip(),
        )
        nb.status = Notebook.Status.DISPONIVEL
        nb.save(update_fields=['status'])
    messages.success(request, f'{nb} reparado e disponível novamente.')
    return _voltar(request, 'notebooks')


# ---------------------------------------------------------------- empréstimos

@login_required
def emprestimos_lista(request):
    ativos = (Emprestimo.objects.filter(devolvido_em__isnull=True)
              .select_related('notebook', 'registrado_por', 'agendamento')
              .order_by('devolucao_prevista', '-retirado_em'))
    historico = Emprestimo.objects.filter(devolvido_em__isnull=False).select_related(
        'notebook', 'registrado_por', 'recebido_por'
    ).order_by('-devolvido_em')
    q = request.GET.get('q', '').strip()
    if q:
        filtro = Q(pessoa__icontains=q) | Q(notebook__numero__icontains=q) | Q(finalidade__icontains=q)
        ativos, historico = ativos.filter(filtro), historico.filter(filtro)
    pagina = Paginator(historico, 25).get_page(request.GET.get('pagina'))
    return render(request, 'app_laboratory/emprestimos.html', {
        'ativos': ativos, 'pagina': pagina, 'q': q,
    })


@login_required
def emprestimo_novo(request):
    inicial, pre_selecionados = {}, []
    agendamento = None
    if ag_id := request.GET.get('agendamento'):
        agendamento = Agendamento.objects.filter(pk=ag_id).first()
    if agendamento:
        fim = timezone.make_aware(datetime.combine(agendamento.data, agendamento.hora_fim))
        inicial = {
            'pessoa': agendamento.solicitante, 'contato': agendamento.contato,
            'finalidade': agendamento.titulo, 'agendamento': agendamento,
            'devolucao_prevista': fim if fim > timezone.now() else None,
        }
        faltam = max(agendamento.quantidade - agendamento.emprestimos.filter(devolvido_em__isnull=True).count(), 0)
        pre_selecionados = list(Notebook.objects.filter(status=Notebook.Status.DISPONIVEL)
                                .values_list('pk', flat=True)[:faltam])
    elif nb_id := request.GET.get('notebook'):
        pre_selecionados = [int(nb_id)] if nb_id.isdigit() else []

    form = EmprestimoForm(request.POST or None, initial={**inicial, 'notebooks': pre_selecionados})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Revalida dentro da transação para evitar dois gerenciadores emprestando o mesmo notebook
            ids = [nb.pk for nb in form.cleaned_data['notebooks']]
            livres = list(Notebook.objects.select_for_update()
                          .filter(pk__in=ids, status=Notebook.Status.DISPONIVEL))
            if len(livres) != len(ids):
                messages.error(request, 'Algum notebook selecionado acabou de ser emprestado. Revise a seleção.')
                return redirect(request.get_full_path())
            dados = {k: v for k, v in form.cleaned_data.items() if k != 'notebooks'}
            for nb in livres:
                Emprestimo.objects.create(notebook=nb, registrado_por=request.user, **dados)
                nb.status = Notebook.Status.EMPRESTADO
                nb.save(update_fields=['status'])
        nomes = ', '.join(str(nb) for nb in livres)
        messages.success(request, f'Empréstimo registrado para {dados["pessoa"]}: {nomes}.')
        if dados.get('agendamento'):
            return redirect('agenda_detalhe', dados['agendamento'].pk)
        return redirect('emprestimos')

    disponiveis = Notebook.objects.filter(status=Notebook.Status.DISPONIVEL)
    selecionados = {str(v) for v in (form['notebooks'].value() or [])}
    return render(request, 'app_laboratory/emprestimo_form.html', {
        'form': form, 'disponiveis': disponiveis, 'selecionados': selecionados, 'agendamento': agendamento,
    })


def _devolver(emprestimos, usuario):
    agora = timezone.now()
    devolvidos = []
    with transaction.atomic():
        for emp in emprestimos.select_related('notebook'):
            emp.devolvido_em, emp.recebido_por = agora, usuario
            emp.save(update_fields=['devolvido_em', 'recebido_por'])
            if emp.notebook.emprestado:
                emp.notebook.status = Notebook.Status.DISPONIVEL
                emp.notebook.save(update_fields=['status'])
            devolvidos.append(emp)
    return devolvidos


@login_required
@require_POST
def emprestimo_devolver(request, pk):
    qs = Emprestimo.objects.filter(pk=pk, devolvido_em__isnull=True)
    devolvidos = _devolver(qs, request.user)
    if devolvidos:
        messages.success(request, f'Devolução de {devolvidos[0].notebook} registrada.')
    else:
        messages.info(request, 'Esse empréstimo já havia sido encerrado.')
    return _voltar(request, 'emprestimos')


@login_required
@require_POST
def notebook_devolver(request, pk):
    """Atalho usado nos cards de notebook: devolve o empréstimo ativo dele."""
    nb = get_object_or_404(Notebook, pk=pk)
    devolvidos = _devolver(nb.emprestimos.filter(devolvido_em__isnull=True), request.user)
    if devolvidos:
        messages.success(request, f'Devolução de {nb} registrada.')
    return _voltar(request, 'notebooks')


# ---------------------------------------------------------------- agenda

def _parse_data(valor, padrao=None):
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        return padrao


@login_required
def agenda(request):
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get('ano', hoje.year))
        mes = int(request.GET.get('mes', hoje.month))
        date(ano, mes, 1)
    except ValueError:
        ano, mes = hoje.year, hoje.month
    dia_sel = _parse_data(request.GET.get('dia'), hoje if (ano, mes) == (hoje.year, hoje.month) else date(ano, mes, 1))

    semanas = calendar.Calendar(firstweekday=6).monthdatescalendar(ano, mes)
    primeiro, ultimo = semanas[0][0], semanas[-1][-1]
    todos = list(Agendamento.objects.filter(data__range=(primeiro, ultimo)).annotate(retirados=Count('emprestimos')))
    frota = frota_operacional()

    por_dia = {}
    for ag in todos:
        por_dia.setdefault(ag.data, []).append(ag)

    grade = []
    for semana in semanas:
        linha = []
        for d in semana:
            itens = por_dia.get(d, [])
            confirmados = [a for a in itens if not a.cancelado]
            pico = pico_reservado(confirmados, time.min, time.max) if confirmados else 0
            linha.append({
                'data': d, 'fora': d.month != mes, 'hoje': d == hoje, 'passado': d < hoje,
                'selecionado': d == dia_sel, 'itens': itens, 'pico': pico,
                'carga': min(round(100 * pico / frota), 100) if frota else (100 if pico else 0),
            })
        grade.append(linha)

    anterior = date(ano, mes, 1) - timedelta(days=1)
    proximo = date(ano, mes, 28) + timedelta(days=7)
    itens_dia = por_dia.get(dia_sel) or list(Agendamento.objects.filter(data=dia_sel)
                                             .annotate(retirados=Count('emprestimos')))
    return render(request, 'app_laboratory/agenda.html', {
        'grade': grade, 'ano': ano, 'mes': mes, 'mes_nome': MESES[mes - 1],
        'anterior': anterior, 'proximo': proximo, 'hoje': hoje,
        'dia_sel': dia_sel, 'itens_dia': itens_dia, 'frota': frota,
        'dias_semana': ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'],
        'proximos': Agendamento.objects.filter(data__gte=hoje, status=Agendamento.Status.CONFIRMADO)[:5],
    })


@login_required
def agenda_novo(request):
    inicial = {'hora_inicio': '08:00', 'hora_fim': '10:00', 'quantidade': 1}
    if data := _parse_data(request.GET.get('data')):
        inicial['data'] = data
    form = AgendamentoForm(request.POST or None, initial=inicial)
    if request.method == 'POST' and form.is_valid():
        ag = form.save(commit=False)
        ag.criado_por = request.user
        ag.save()
        messages.success(request, f'Agendamento "{ag.titulo}" criado para {ag.data:%d/%m/%Y}.')
        return redirect(f"{reverse('agenda')}?ano={ag.data.year}&mes={ag.data.month}&dia={ag.data.isoformat()}")
    return render(request, 'app_laboratory/agenda_form.html', {'form': form, 'frota': frota_operacional()})


@login_required
def agenda_editar(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    form = AgendamentoForm(request.POST or None, instance=ag)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Agendamento atualizado.')
        return redirect('agenda_detalhe', ag.pk)
    return render(request, 'app_laboratory/agenda_form.html', {'form': form, 'ag': ag, 'frota': frota_operacional()})


@login_required
def agenda_detalhe(request, pk):
    ag = get_object_or_404(Agendamento.objects.select_related('criado_por'), pk=pk)
    emprestimos = ag.emprestimos.select_related('notebook').order_by('devolvido_em', 'notebook__numero')
    ativos = [e for e in emprestimos if e.ativo]
    return render(request, 'app_laboratory/agenda_detalhe.html', {
        'ag': ag, 'emprestimos': emprestimos, 'ativos': ativos,
        'faltam': max(ag.quantidade - len(ativos), 0) if not ag.passado else 0,
        'disponiveis_agora': Notebook.objects.filter(status=Notebook.Status.DISPONIVEL).count(),
    })


@login_required
@require_POST
def agenda_cancelar(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    ag.status = Agendamento.Status.CANCELADO
    ag.save(update_fields=['status'])
    messages.warning(request, f'Agendamento "{ag.titulo}" cancelado.')
    return redirect('agenda_detalhe', ag.pk)


@login_required
@require_POST
def agenda_reativar(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    livres = capacidade_livre(ag.data, ag.hora_inicio, ag.hora_fim, excluir=ag)
    if ag.quantidade > livres:
        messages.error(request, f'Não há notebooks suficientes nesse horário (livres: {livres}).')
    else:
        ag.status = Agendamento.Status.CONFIRMADO
        ag.save(update_fields=['status'])
        messages.success(request, 'Agendamento reativado.')
    return redirect('agenda_detalhe', ag.pk)


@login_required
@require_POST
def agenda_devolver(request, pk):
    ag = get_object_or_404(Agendamento, pk=pk)
    devolvidos = _devolver(ag.emprestimos.filter(devolvido_em__isnull=True), request.user)
    messages.success(request, f'{len(devolvidos)} notebook(s) devolvido(s).')
    return redirect('agenda_detalhe', ag.pk)


@login_required
def agenda_disponibilidade(request):
    """JSON usado pelo formulário de agendamento para mostrar a disponibilidade ao vivo."""
    data = _parse_data(request.GET.get('data'))
    try:
        inicio = time.fromisoformat(request.GET.get('inicio', ''))
        fim = time.fromisoformat(request.GET.get('fim', ''))
    except ValueError:
        return JsonResponse({'erro': 'parâmetros inválidos'}, status=400)
    if not data or fim <= inicio:
        return JsonResponse({'erro': 'parâmetros inválidos'}, status=400)
    excluir = Agendamento.objects.filter(pk=request.GET.get('excluir') or 0).first()
    outros = [a for a in agendamentos_confirmados(data, excluir) if a.hora_inicio < fim and a.hora_fim > inicio]
    return JsonResponse({
        'frota': frota_operacional(),
        'livres': capacidade_livre(data, inicio, fim, excluir),
        'conflitos': [
            {'titulo': a.titulo, 'inicio': a.hora_inicio.strftime('%H:%M'),
             'fim': a.hora_fim.strftime('%H:%M'), 'quantidade': a.quantidade}
            for a in outros
        ],
    })
