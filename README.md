# NOTE//LAB — controle de notebooks do laboratório

Sistema Django para a equipe do laboratório controlar empréstimos, baixas (notebooks quebrados) e agendamentos de notebooks.

## Funcionalidades

- **Painel**: indicadores animados (inventário, disponíveis, emprestados, quebrados, taxa de uso), alerta de devoluções atrasadas, agenda do dia, próximos 7 dias e feed de atividade (quem fez o quê).
- **Notebooks**: grade ou lista, filtros por status, busca instantânea, cadastro individual ou **em lote** (ex.: `NB-01` a `NB-30`), página de detalhe com histórico completo.
- **Empréstimos**: saída de **vários notebooks de uma vez** para a mesma pessoa, devolução prevista, destaque de atrasados, histórico paginado e registro de qual gerenciador entregou/recebeu.
- **Baixa de notebook quebrado**: exige o motivo e a **senha do gerenciador** como autorização. O notebook fica destacado em **vermelho** (com brilho pulsante), sai de circulação e não conta para a agenda até ser marcado como reparado. Se estava emprestado, o empréstimo é encerrado.
- **Agenda**: calendário mensal com barra de ocupação por dia, cadastro com **disponibilidade em tempo real** (considera outros agendamentos sobrepostos e notebooks quebrados) e bloqueio de reservas acima da capacidade. No dia, o botão "Registrar retirada" abre o empréstimo já preenchido e com os notebooks pré-selecionados; depois é possível devolver todos de uma vez.

## Rodando localmente

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
set DJANGO_DEBUG=1              # Linux/macOS: export DJANGO_DEBUG=1
python manage.py migrate
python manage.py createsuperuser
python manage.py popular_demo   # opcional: dados fictícios para testar
python manage.py runserver
```

Crie um usuário para cada gerenciador em `/admin/` (ou com `createsuperuser`).

## Testes

```bash
python manage.py test app_laboratory
```

## Deploy (PythonAnywhere)

Depois de atualizar o código no servidor:

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

A migração `0003` converte os empréstimos da versão anterior (`esta_emprestado`/`pessoa_emprestada`) em registros de empréstimo, sem perder dados.

Variáveis de ambiente opcionais: `DJANGO_SECRET_KEY` (recomendado em produção) e `DJANGO_DEBUG=1` (apenas em desenvolvimento).
