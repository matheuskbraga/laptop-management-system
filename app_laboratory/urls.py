from django.urls import path
from . import views

urlpatterns = [
    path('', views.listar_notebooks, name='listar_notebooks'), # padrão inicial da página
    path('novo/', views.criar_notebook, name='criar_notebook'),
    path('<int:pk>/emprestar/', views.emprestar_notebook, name='emprestar_notebook'),
    path('<int:pk>/devolver/', views.devolver_notebook, name='devolver_notebook'),
    path('<int:pk>/remover/', views.remover_notebook, name='remover_notebook'),
]