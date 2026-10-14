import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def migrar_emprestimos_existentes(apps, schema_editor):
    """Converte o antigo par (esta_emprestado, pessoa_emprestada) em status + Emprestimo."""
    Notebook = apps.get_model('app_laboratory', 'Notebook')
    Emprestimo = apps.get_model('app_laboratory', 'Emprestimo')
    for nb in Notebook.objects.filter(esta_emprestado=True):
        nb.status = 'emprestado'
        nb.save(update_fields=['status'])
        Emprestimo.objects.create(
            notebook=nb,
            pessoa=nb.pessoa_emprestada or 'Não informado',
            observacoes='Empréstimo migrado da versão anterior do sistema.',
        )


def reverter_emprestimos(apps, schema_editor):
    Notebook = apps.get_model('app_laboratory', 'Notebook')
    for nb in Notebook.objects.all():
        ativo = nb.emprestimos.filter(devolvido_em__isnull=True).first()
        nb.esta_emprestado = ativo is not None
        nb.pessoa_emprestada = ativo.pessoa if ativo else None
        nb.save(update_fields=['esta_emprestado', 'pessoa_emprestada'])


class Migration(migrations.Migration):

    dependencies = [
        ('app_laboratory', '0002_rename_notebooks_notebook'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(name='notebook', options={'ordering': ['numero']}),
        migrations.AddField(
            model_name='notebook',
            name='modelo',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='notebook',
            name='status',
            field=models.CharField(
                choices=[('disponivel', 'Disponível'), ('emprestado', 'Emprestado'), ('quebrado', 'Quebrado')],
                default='disponivel',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='notebook',
            name='observacoes',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='notebook',
            name='criado_em',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.CreateModel(
            name='Agendamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=150, verbose_name='título')),
                ('solicitante', models.CharField(max_length=150)),
                ('contato', models.CharField(blank=True, help_text='E-mail, telefone, setor ou turma', max_length=150)),
                ('tipo', models.CharField(
                    choices=[('aula', 'Aula'), ('tarefa', 'Tarefa'), ('projeto', 'Projeto'),
                             ('formacao', 'Formação'), ('evento', 'Evento'), ('outro', 'Outro')],
                    default='aula', max_length=20,
                )),
                ('data', models.DateField()),
                ('hora_inicio', models.TimeField(verbose_name='início')),
                ('hora_fim', models.TimeField(verbose_name='fim')),
                ('quantidade', models.PositiveIntegerField()),
                ('observacoes', models.TextField(blank=True, verbose_name='observações')),
                ('status', models.CharField(
                    choices=[('confirmado', 'Confirmado'), ('cancelado', 'Cancelado')],
                    default='confirmado', max_length=20,
                )),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('criado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['data', 'hora_inicio']},
        ),
        migrations.CreateModel(
            name='Emprestimo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pessoa', models.CharField(max_length=150)),
                ('contato', models.CharField(blank=True, max_length=150)),
                ('finalidade', models.CharField(blank=True, max_length=200)),
                ('retirado_em', models.DateTimeField(default=django.utils.timezone.now)),
                ('devolucao_prevista', models.DateTimeField(blank=True, null=True, verbose_name='devolução prevista')),
                ('devolvido_em', models.DateTimeField(blank=True, null=True)),
                ('observacoes', models.TextField(blank=True)),
                ('agendamento', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='emprestimos', to='app_laboratory.agendamento',
                )),
                ('notebook', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='emprestimos', to='app_laboratory.notebook',
                )),
                ('recebido_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
                ('registrado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'verbose_name': 'empréstimo', 'ordering': ['-retirado_em']},
        ),
        migrations.CreateModel(
            name='Baixa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('motivo', models.TextField()),
                ('registrado_em', models.DateTimeField(default=django.utils.timezone.now)),
                ('resolvido_em', models.DateTimeField(blank=True, null=True)),
                ('solucao', models.TextField(blank=True, verbose_name='solução')),
                ('notebook', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='baixas', to='app_laboratory.notebook',
                )),
                ('registrado_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
                ('resolvido_por', models.ForeignKey(
                    blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                    related_name='+', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-registrado_em']},
        ),
        migrations.RunPython(migrar_emprestimos_existentes, reverter_emprestimos),
        migrations.RemoveField(model_name='notebook', name='esta_emprestado'),
        migrations.RemoveField(model_name='notebook', name='pessoa_emprestada'),
    ]
