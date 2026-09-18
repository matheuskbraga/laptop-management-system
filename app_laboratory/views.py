from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Notebook


@login_required
# Create your views here.
def listar_notebooks(request):
    notebooks = Notebook.objects.all().order_by('numero')
    return render(request, 'app_laboratory/lista.html', {'notebooks': notebooks})


@login_required
def criar_notebook(request):
    if request.method == 'POST':
        numero = request.POST.get('numero')
        Notebook.objects.create(numero=numero)
        return redirect('listar_notebooks')
    return render(request, 'app_laboratory/form_notebook.html')


@login_required
def emprestar_notebook(request, pk):
    notebook = get_object_or_404(Notebook, pk=pk)
    if request.method == 'POST':
        notebook.pessoa_emprestada = request.POST.get('pessoa')
        notebook.esta_emprestado = True
        notebook.save()
        return redirect('listar_notebooks')
    return render(request, 'app_laboratory/form_emprestimo.html', {'notebook': notebook})


@login_required
def devolver_notebook(request, pk):
    notebook = get_object_or_404(Notebook, pk=pk)
    notebook.pessoa_emprestada = None
    notebook.esta_emprestado = False
    notebook.save()
    return redirect('listar_notebooks')


@login_required
def remover_notebook(request, pk):
    notebook = get_object_or_404(Notebook, pk=pk)
    notebook.delete()
    return redirect('listar_notebooks')