from django.utils import timezone

from .models import Agendamento, Emprestimo, Notebook


def contadores(request):
    """Números exibidos como badges no menu lateral."""
    if not request.user.is_authenticated:
        return {}
    return {
        'menu_quebrados': Notebook.objects.filter(status=Notebook.Status.QUEBRADO).count(),
        'menu_atrasados': Emprestimo.objects.filter(
            devolvido_em__isnull=True, devolucao_prevista__lt=timezone.now()
        ).count(),
        'menu_agenda_hoje': Agendamento.objects.filter(
            data=timezone.localdate(), status=Agendamento.Status.CONFIRMADO
        ).count(),
    }
