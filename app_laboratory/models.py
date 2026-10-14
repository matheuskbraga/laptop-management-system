from django.conf import settings
from django.db import models
from django.utils import timezone


class Notebook(models.Model):
    class Status(models.TextChoices):
        DISPONIVEL = 'disponivel', 'Disponível'
        EMPRESTADO = 'emprestado', 'Emprestado'
        QUEBRADO = 'quebrado', 'Quebrado'

    numero = models.CharField(max_length=50, unique=True)
    modelo = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DISPONIVEL)
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return self.numero

    @property
    def emprestimo_ativo(self):
        # Usa o prefetch da view quando disponível, evitando uma query por notebook
        if hasattr(self, '_emprestimos_ativos'):
            return self._emprestimos_ativos[0] if self._emprestimos_ativos else None
        return self.emprestimos.filter(devolvido_em__isnull=True).first()

    @property
    def baixa_ativa(self):
        if hasattr(self, '_baixas_ativas'):
            return self._baixas_ativas[0] if self._baixas_ativas else None
        return self.baixas.filter(resolvido_em__isnull=True).first()

    @property
    def disponivel(self):
        return self.status == self.Status.DISPONIVEL

    @property
    def emprestado(self):
        return self.status == self.Status.EMPRESTADO

    @property
    def quebrado(self):
        return self.status == self.Status.QUEBRADO


class Agendamento(models.Model):
    class Tipo(models.TextChoices):
        AULA = 'aula', 'Aula'
        TAREFA = 'tarefa', 'Tarefa'
        PROJETO = 'projeto', 'Projeto'
        FORMACAO = 'formacao', 'Formação'
        EVENTO = 'evento', 'Evento'
        OUTRO = 'outro', 'Outro'

    class Status(models.TextChoices):
        CONFIRMADO = 'confirmado', 'Confirmado'
        CANCELADO = 'cancelado', 'Cancelado'

    titulo = models.CharField('título', max_length=150)
    solicitante = models.CharField(max_length=150)
    contato = models.CharField(max_length=150, blank=True, help_text='E-mail, telefone, setor ou turma')
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.AULA)
    data = models.DateField()
    hora_inicio = models.TimeField('início')
    hora_fim = models.TimeField('fim')
    quantidade = models.PositiveIntegerField()
    observacoes = models.TextField('observações', blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CONFIRMADO)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['data', 'hora_inicio']

    def __str__(self):
        return f'{self.titulo} ({self.data:%d/%m/%Y})'

    @property
    def cancelado(self):
        return self.status == self.Status.CANCELADO

    @property
    def passado(self):
        agora = timezone.localtime()
        return (self.data, self.hora_fim) < (agora.date(), agora.time())

    @property
    def em_andamento(self):
        agora = timezone.localtime()
        return self.data == agora.date() and self.hora_inicio <= agora.time() < self.hora_fim


class Emprestimo(models.Model):
    notebook = models.ForeignKey(Notebook, on_delete=models.CASCADE, related_name='emprestimos')
    pessoa = models.CharField(max_length=150)
    contato = models.CharField(max_length=150, blank=True)
    finalidade = models.CharField(max_length=200, blank=True)
    agendamento = models.ForeignKey(
        Agendamento, on_delete=models.SET_NULL, null=True, blank=True, related_name='emprestimos'
    )
    retirado_em = models.DateTimeField(default=timezone.now)
    devolucao_prevista = models.DateTimeField('devolução prevista', null=True, blank=True)
    devolvido_em = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    recebido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )

    class Meta:
        ordering = ['-retirado_em']
        verbose_name = 'empréstimo'

    def __str__(self):
        return f'{self.notebook} → {self.pessoa}'

    @property
    def ativo(self):
        return self.devolvido_em is None

    @property
    def atrasado(self):
        return self.ativo and self.devolucao_prevista is not None and self.devolucao_prevista < timezone.now()


class Baixa(models.Model):
    """Registro de um notebook dado como quebrado (e, depois, do seu reparo)."""

    notebook = models.ForeignKey(Notebook, on_delete=models.CASCADE, related_name='baixas')
    motivo = models.TextField()
    registrado_em = models.DateTimeField(default=timezone.now)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    resolvido_em = models.DateTimeField(null=True, blank=True)
    resolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    solucao = models.TextField('solução', blank=True)

    class Meta:
        ordering = ['-registrado_em']

    def __str__(self):
        return f'Baixa {self.notebook} em {self.registrado_em:%d/%m/%Y}'

    @property
    def ativa(self):
        return self.resolvido_em is None
