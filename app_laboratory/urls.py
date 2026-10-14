from django.urls import path
from . import views

urlpatterns = [
    path('', views.painel, name='painel'),

    path('notebooks/', views.notebooks_lista, name='notebooks'),
    path('notebooks/novo/', views.notebook_novo, name='notebook_novo'),
    path('notebooks/<int:pk>/', views.notebook_detalhe, name='notebook_detalhe'),
    path('notebooks/<int:pk>/editar/', views.notebook_editar, name='notebook_editar'),
    path('notebooks/<int:pk>/remover/', views.notebook_remover, name='notebook_remover'),
    path('notebooks/<int:pk>/baixa/', views.notebook_baixa, name='notebook_baixa'),
    path('notebooks/<int:pk>/reparar/', views.notebook_reparar, name='notebook_reparar'),
    path('notebooks/<int:pk>/devolver/', views.notebook_devolver, name='notebook_devolver'),

    path('emprestimos/', views.emprestimos_lista, name='emprestimos'),
    path('emprestimos/novo/', views.emprestimo_novo, name='emprestimo_novo'),
    path('emprestimos/<int:pk>/devolver/', views.emprestimo_devolver, name='emprestimo_devolver'),

    path('agenda/', views.agenda, name='agenda'),
    path('agenda/novo/', views.agenda_novo, name='agenda_novo'),
    path('agenda/disponibilidade/', views.agenda_disponibilidade, name='agenda_disponibilidade'),
    path('agenda/<int:pk>/', views.agenda_detalhe, name='agenda_detalhe'),
    path('agenda/<int:pk>/editar/', views.agenda_editar, name='agenda_editar'),
    path('agenda/<int:pk>/cancelar/', views.agenda_cancelar, name='agenda_cancelar'),
    path('agenda/<int:pk>/reativar/', views.agenda_reativar, name='agenda_reativar'),
    path('agenda/<int:pk>/devolver/', views.agenda_devolver, name='agenda_devolver'),
]
