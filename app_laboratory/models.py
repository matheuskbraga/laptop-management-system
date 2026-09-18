from django.db import models

# Create your models here.
class Notebook(models.Model):
    numero = models.CharField(max_length=50, unique=True,)
    pessoa_emprestada = models.CharField(max_length=150, blank=True, null=True,)
    esta_emprestado = models.BooleanField(default=False, verbose_name="Está Emprestado?")

    def __str__(self):
        return self.numero

    '''
    def __str__(self):
            status = "Emprestado" if self.esta_emprestado else "Disponível"
            return f"Notebook {self.numero} - {status}"
    '''
    