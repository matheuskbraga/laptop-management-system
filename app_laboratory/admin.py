from django.contrib import admin
from .models import Agendamento, Baixa, Emprestimo, Notebook


@admin.register(Notebook)
class NotebookAdmin(admin.ModelAdmin):
    list_display = ['numero', 'modelo', 'status']
    list_filter = ['status']
    search_fields = ['numero', 'modelo']


@admin.register(Emprestimo)
class EmprestimoAdmin(admin.ModelAdmin):
    list_display = ['notebook', 'pessoa', 'retirado_em', 'devolucao_prevista', 'devolvido_em']
    list_filter = ['devolvido_em']
    search_fields = ['pessoa', 'notebook__numero']
    date_hierarchy = 'retirado_em'


@admin.register(Baixa)
class BaixaAdmin(admin.ModelAdmin):
    list_display = ['notebook', 'registrado_em', 'registrado_por', 'resolvido_em']
    search_fields = ['notebook__numero', 'motivo']


@admin.register(Agendamento)
class AgendamentoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'data', 'hora_inicio', 'hora_fim', 'quantidade', 'solicitante', 'status']
    list_filter = ['status', 'tipo']
    date_hierarchy = 'data'
