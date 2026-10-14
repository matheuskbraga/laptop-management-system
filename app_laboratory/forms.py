from django import forms
from django.utils import timezone

from .models import Agendamento, Emprestimo, Notebook
from .services import capacidade_livre

DATETIME_LOCAL = '%Y-%m-%dT%H:%M'


class NotebookForm(forms.ModelForm):
    class Meta:
        model = Notebook
        fields = ['numero', 'modelo', 'observacoes']
        labels = {'numero': 'Número / identificação', 'modelo': 'Modelo', 'observacoes': 'Observações'}
        widgets = {
            'numero': forms.TextInput(attrs={'placeholder': 'Ex.: NB-01', 'autofocus': True}),
            'modelo': forms.TextInput(attrs={'placeholder': 'Ex.: Dell Latitude 3420'}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Carregador, etiqueta, detalhes...'}),
        }


class NotebookLoteForm(forms.Form):
    """Cadastro de vários notebooks de uma vez: prefixo + intervalo numérico."""

    prefixo = forms.CharField(max_length=40, initial='NB-', required=False)
    inicio = forms.IntegerField(min_value=0, initial=1, label='De')
    fim = forms.IntegerField(min_value=0, initial=10, label='Até')
    digitos = forms.IntegerField(min_value=1, max_value=6, initial=2, label='Dígitos')
    modelo = forms.CharField(max_length=100, required=False)

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('inicio'), dados.get('fim')
        if inicio is not None and fim is not None:
            if fim < inicio:
                raise forms.ValidationError('O número final deve ser maior ou igual ao inicial.')
            if fim - inicio >= 200:
                raise forms.ValidationError('Cadastre no máximo 200 notebooks por vez.')
        return dados

    def numeros(self):
        d = self.cleaned_data
        return [f"{d['prefixo']}{n:0{d['digitos']}d}" for n in range(d['inicio'], d['fim'] + 1)]


class EmprestimoForm(forms.ModelForm):
    notebooks = forms.ModelMultipleChoiceField(
        queryset=Notebook.objects.filter(status=Notebook.Status.DISPONIVEL),
        widget=forms.CheckboxSelectMultiple,
        error_messages={'required': 'Selecione pelo menos um notebook.'},
    )

    class Meta:
        model = Emprestimo
        fields = ['pessoa', 'contato', 'finalidade', 'devolucao_prevista', 'agendamento', 'observacoes']
        labels = {
            'pessoa': 'Quem está retirando',
            'contato': 'Contato / setor / turma',
            'finalidade': 'Finalidade',
            'devolucao_prevista': 'Devolução prevista',
            'agendamento': 'Vincular a um agendamento',
            'observacoes': 'Observações',
        }
        widgets = {
            'pessoa': forms.TextInput(attrs={'placeholder': 'Nome completo', 'autofocus': True}),
            'contato': forms.TextInput(attrs={'placeholder': 'Opcional'}),
            'finalidade': forms.TextInput(attrs={'placeholder': 'Ex.: aula de robótica'}),
            'devolucao_prevista': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DATETIME_LOCAL),
            'observacoes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Opcional'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.localdate()
        self.fields['agendamento'].queryset = Agendamento.objects.filter(
            status=Agendamento.Status.CONFIRMADO, data__gte=hoje
        )
        self.fields['agendamento'].required = False
        self.fields['agendamento'].empty_label = '— Nenhum —'

    def clean_devolucao_prevista(self):
        valor = self.cleaned_data.get('devolucao_prevista')
        if valor and valor < timezone.now():
            raise forms.ValidationError('A devolução prevista precisa estar no futuro.')
        return valor


class AgendamentoForm(forms.ModelForm):
    class Meta:
        model = Agendamento
        fields = [
            'titulo', 'tipo', 'solicitante', 'contato', 'data',
            'hora_inicio', 'hora_fim', 'quantidade', 'observacoes',
        ]
        labels = {'titulo': 'Título', 'quantidade': 'Quantidade de notebooks'}
        widgets = {
            'titulo': forms.TextInput(attrs={'placeholder': 'Ex.: Formação de professores', 'autofocus': True}),
            'solicitante': forms.TextInput(attrs={'placeholder': 'Quem está pedindo'}),
            'contato': forms.TextInput(attrs={'placeholder': 'Opcional'}),
            'data': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'hora_fim': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'quantidade': forms.NumberInput(attrs={'min': 1}),
            'observacoes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Sala, softwares necessários, etc.'}),
        }

    def clean_quantidade(self):
        qtd = self.cleaned_data['quantidade']
        if qtd < 1:
            raise forms.ValidationError('Informe pelo menos 1 notebook.')
        return qtd

    def clean(self):
        dados = super().clean()
        data, inicio, fim, qtd = (dados.get(k) for k in ('data', 'hora_inicio', 'hora_fim', 'quantidade'))
        if not all([data, inicio, fim, qtd]):
            return dados
        if fim <= inicio:
            self.add_error('hora_fim', 'O horário final deve ser depois do inicial.')
            return dados
        if self.instance.pk is None and data < timezone.localdate():
            self.add_error('data', 'Não é possível agendar em uma data que já passou.')
            return dados
        livres = capacidade_livre(data, inicio, fim, excluir=self.instance if self.instance.pk else None)
        if qtd > livres:
            self.add_error(
                'quantidade',
                f'Só há {livres} notebook(s) livre(s) nesse horário, considerando os outros agendamentos.',
            )
        return dados


class BaixaForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), max_length=1000)
    senha = forms.CharField(widget=forms.PasswordInput, label='Sua senha')

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_senha(self):
        senha = self.cleaned_data['senha']
        if not self.user or not self.user.check_password(senha):
            raise forms.ValidationError('Senha incorreta. A baixa não foi autorizada.')
        return senha
