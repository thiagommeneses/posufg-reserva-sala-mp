#!/usr/bin/env bash
#
# commitar-fases.sh — transforma a árvore de trabalho do redesign V2 numa
# sequência de commits, um por fase, na ordem em que as fases foram entregues.
#
# ---------------------------------------------------------------------------
# LEIA ISTO ANTES DE RODAR
#
# Este script NÃO reconstrói a história real, e não tem como. O conteúdo dos
# arquivos na sua árvore é o estado final (Fase 24); o que o script faz é
# **agrupar** esse estado final em commits, usando a lista de arquivos de cada
# pacote entregue para decidir o que entra em qual commit.
#
# Na prática: cada arquivo é commitado na primeira fase que o tocou. Um arquivo
# mexido na Fase 4 e de novo na Fase 20 aparece só no commit da Fase 4, já com o
# conteúdo da Fase 24. O log fica legível e rastreável; os diffs intermediários
# não são fotografias de época. Isso é uma limitação honesta, não um bug.
#
# Os pacotes da Fase 1 e da Fase 2 não existem mais. Os arquivos que só elas
# tocaram caem no commit final de sobra, que é onde vai parar tudo que não
# estiver em nenhum manifesto.
#
# O `--no-verify` é deliberado: o `.pre-commit-config.yaml` roda `uv run pytest`
# em todo commit (`always_run: true`), e a suíte leva ~10 minutos. Trinta
# commits seriam mais de cinco horas. A verificação acontece uma vez, no fim,
# sobre o estado que realmente importa — que é o mesmo antes e depois, já que
# nenhum arquivo é modificado aqui.
#
# ---------------------------------------------------------------------------
# USO
#
#   ./commitar-fases.sh                  # cria a branch, mostra o plano, pergunta
#   ./commitar-fases.sh --dry-run        # só mostra o que faria; não toca em nada
#   ./commitar-fases.sh -y               # não pergunta
#   ./commitar-fases.sh --sem-branch     # commita na branch atual
#   ./commitar-fases.sh --branch NOME    # usa outro nome de branch
#   ./commitar-fases.sh --sem-teste      # pula o `make test` do fim
#
# Rode na raiz do projeto (a pasta que tem `manage.py`).
# ---------------------------------------------------------------------------

set -euo pipefail

BRANCH="redesign-v2"
CRIAR_BRANCH=1
CONFIRMAR=1
DRY_RUN=0
RODAR_TESTE=1
COMANDO_TESTE="make test"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)    DRY_RUN=1 ;;
        -y|--sim)     CONFIRMAR=0 ;;
        --sem-branch) CRIAR_BRANCH=0 ;;
        --sem-teste)  RODAR_TESTE=0 ;;
        --branch)     BRANCH="${2:?--branch precisa de um nome}"; shift ;;
        -h|--help)    sed -n '2,45p' "$0"; exit 0 ;;
        *)            echo "opção desconhecida: $1 (use --help)" >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Cores, só quando a saída é um terminal.
# ---------------------------------------------------------------------------
if [[ -t 1 ]]; then
    NEGRITO=$'\e[1m'; APAGADO=$'\e[2m'; VERDE=$'\e[32m'
    AMARELO=$'\e[33m'; VERMELHO=$'\e[31m'; FIM=$'\e[0m'
else
    NEGRITO=""; APAGADO=""; VERDE=""; AMARELO=""; VERMELHO=""; FIM=""
fi

erro()  { echo "${VERMELHO}erro:${FIM} $*" >&2; exit 1; }
aviso() { echo "${AMARELO}aviso:${FIM} $*" >&2; }

# ---------------------------------------------------------------------------
# Verificações de segurança. Nenhuma delas é paranoia: cada uma corresponde a
# uma forma real de este script fazer estrago na árvore errada.
# ---------------------------------------------------------------------------
[[ -f manage.py && -f pyproject.toml ]] \
    || erro "rode na raiz do projeto (a pasta com manage.py e pyproject.toml)"

git rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || erro "esta pasta não é um repositório git"

[[ "$(git rev-parse --show-toplevel)" == "$PWD" ]] \
    || erro "rode na raiz do repositório: $(git rev-parse --show-toplevel)"

git rev-parse HEAD >/dev/null 2>&1 \
    || erro "o repositório não tem nenhum commit ainda — faça o commit inicial da base antes"

if [[ -z "$(git status --porcelain)" ]]; then
    erro "não há nada para commitar: a árvore está limpa"
fi

if [[ -n "$(git diff --cached --name-only)" ]]; then
    erro "há arquivos já no stage. Rode 'git reset' antes, para o script controlar o que entra em cada commit"
fi

# ---------------------------------------------------------------------------
# As fases, na ordem de entrega. Cada bloco é: nome, mensagem, arquivos.
#
# As listas vêm dos manifestos dos próprios pacotes .tgz entregues — não foram
# escritas à mão nem inferidas do conteúdo.
# ---------------------------------------------------------------------------
declare -a NOMES=() MENSAGENS=() ARQUIVOS=()

fase() {
    local nome="$1" mensagem="$2"; shift 2
    NOMES+=("$nome")
    MENSAGENS+=("$mensagem")
    ARQUIVOS+=("$*")
}

fase "Fase 0" \
"refactor: centraliza as regras em validators e serve fontes e HTMX localmente" \
    admin_dashboard/tests.py admin_dashboard/views.py assets/css/source.css \
    config/settings.py core/serializers.py core/tests.py \
    reservations/serializers.py reservations/services.py reservations/tests.py \
    reservations/validators.py reservations/views.py \
    spaces/serializers.py spaces/tests.py spaces/views.py \
    static/css/tailwind.css static/fonts static/img/logo.png static/js/htmx.min.js \
    templates/base.html templates/spaces/_availability.html

fase "Fase 0b" \
"chore: prepara a implantação com Dockerfile, compose de produção e checagens" \
    .dockerignore .env.example .gitignore Dockerfile README.md \
    config/settings.py config/urls.py core/test_deployment.py \
    docker-compose.prod.yml pyproject.toml \
    reservations/tests.py spaces/tests.py spaces/views.py uv.lock

fase "Fase 3" \
"feat: tipos de espaço com catálogo inicial e CRUD administrativo" \
    admin_dashboard/forms.py admin_dashboard/urls.py admin_dashboard/views.py \
    core/tests.py \
    spaces/management spaces/migrations/0004_spacetype_space_space_type.py \
    spaces/migrations/0005_spacetype_catalogo_inicial.py \
    spaces/models.py spaces/serializers.py spaces/test_space_type.py \
    spaces/validators.py spaces/views.py static/css/tailwind.css \
    templates/admin_dashboard/space_list.html \
    templates/admin_dashboard/space_type_form.html \
    templates/admin_dashboard/space_type_list.html \
    templates/base_admin.html templates/partials/_icon.html \
    templates/spaces/_space_list_results.html \
    templates/spaces/space_detail.html templates/spaces/space_list.html

fase "Fase 4" \
"feat: política de reserva e disponibilidade derivada dos horários configurados" \
    admin_dashboard/forms.py admin_dashboard/urls.py admin_dashboard/views.py \
    core/tests.py reservations/availability.py \
    reservations/migrations/0002_bookingpolicy.py \
    reservations/migrations/0003_bookingpolicy_padrao.py \
    reservations/models.py reservations/services.py \
    reservations/test_availability.py reservations/tests.py \
    reservations/validators.py reservations/views.py \
    spaces/tests.py spaces/validators.py spaces/views.py \
    static/css/tailwind.css \
    templates/admin_dashboard/booking_policy_form.html \
    templates/base_admin.html templates/partials/_availability_badge.html \
    templates/partials/_icon.html templates/spaces/_availability.html \
    templates/spaces/_space_list_results.html templates/spaces/space_detail.html

fase "Fase 5" \
"feat: equipamentos com categoria, ícone e destaque na busca de espaços" \
    admin_dashboard/forms.py admin_dashboard/urls.py admin_dashboard/views.py \
    assets/css/source.css core/tests.py spaces/admin.py \
    spaces/management/commands/sugerir_atributos_em_destaque.py \
    spaces/migrations/0006_alter_attribute_options_attribute_category_and_more.py \
    spaces/migrations/0007_atributos_icones.py \
    spaces/models.py spaces/test_attributes.py spaces/validators.py spaces/views.py \
    static/css/tailwind.css \
    templates/admin_dashboard/attribute_form.html \
    templates/admin_dashboard/attribute_list.html \
    templates/base_admin.html templates/partials/_icon.html \
    templates/spaces/_attribute_checkbox.html \
    templates/spaces/_space_list_results.html templates/spaces/space_list.html

fase "Fase 6" \
"feat: tela de início com a próxima reserva e as regras que valem hoje" \
    accounts/tests.py accounts/views.py \
    core/dashboard.py core/test_inicio.py core/tests.py core/urls.py core/views.py \
    reservations/services.py reservations/views.py spaces/validators.py \
    static/css/tailwind.css templates/base_user.html templates/core/inicio.html \
    templates/partials/_icon.html

fase "Fase 7" \
"feat: passo 1 da reserva com resumo da seleção que sobrevive à navegação" \
    spaces/test_passo1.py spaces/tests.py spaces/views.py static/css/tailwind.css \
    templates/partials/_availability_badge.html \
    templates/spaces/_selection_summary.html \
    templates/spaces/_space_list_fragment.html \
    templates/spaces/_space_list_results.html templates/spaces/space_list.html

fase "Fase 8" \
"feat: a busca com IA passa a entender faixa de horário na frase" \
    ai_assistant/services.py ai_assistant/test_busca_temporal.py \
    reservations/availability.py spaces/test_passo1.py spaces/tests.py spaces/views.py \
    static/css/tailwind.css templates/partials/_availability_badge.html \
    templates/spaces/_space_list_results.html templates/spaces/space_list.html

fase "Fase 9" \
"feat: passo 2 oferece alternativas quando o horário pedido não cabe" \
    reservations/availability.py spaces/test_passo2.py spaces/views.py \
    static/css/tailwind.css templates/spaces/_alternativas.html \
    templates/spaces/_availability.html templates/spaces/_selection_summary.html \
    templates/spaces/space_detail.html

fase "Fase 10" \
"feat: perfil do usuário e detalhes da reserva (assunto, participantes, observações)" \
    accounts/admin.py accounts/forms.py accounts/migrations/0001_initial.py \
    accounts/models.py accounts/urls.py accounts/views.py core/tests.py \
    reservations/admin.py \
    reservations/migrations/0004_reservation_attendee_count_reservation_notes_and_more.py \
    reservations/models.py reservations/serializers.py reservations/services.py \
    reservations/test_detalhes.py reservations/tests.py reservations/validators.py \
    reservations/views.py static/css/tailwind.css \
    templates/accounts/profile.html templates/base_user.html \
    templates/reservations/reservation_detail.html \
    templates/reservations/reservation_form.html

fase "Fase 11" \
"feat: catálogo de serviços e fila de atendimento da administração" \
    admin_dashboard/forms.py admin_dashboard/urls.py admin_dashboard/views.py \
    config/settings.py core/tests.py reservations/services.py reservations/views.py \
    services spaces/test_passo1.py static/css/tailwind.css \
    templates/admin_dashboard/service_queue.html \
    templates/admin_dashboard/service_type_form.html \
    templates/admin_dashboard/service_type_list.html \
    templates/base_admin.html templates/reservations/_service_picker.html \
    templates/reservations/reservation_detail.html \
    templates/reservations/reservation_form.html

fase "Fase 11b" \
"test: corrige a asserção do próximo horário livre no passo 1" \
    spaces/test_passo1.py

fase "Fase 12" \
"feat: solicitação de serviços junto com a criação da reserva" \
    reservations/services.py reservations/validators.py reservations/views.py \
    services/test_servicos.py static/css/tailwind.css \
    templates/components/_reservation_summary.html \
    templates/reservations/_service_picker.html \
    templates/reservations/reservation_form.html

fase "Fase 13" \
"feat: tela de revisão antes de confirmar a reserva" \
    config/urls.py reservations/views.py services/test_servicos.py \
    spaces/validators.py spaces/views.py static/css/tailwind.css \
    templates/partials/_icon.html templates/reservations/reservation_form.html \
    templates/reservations/reservation_review.html

fase "Fase 14" \
"feat: resumo fixo no rodapé e número de participantes opcional" \
    reservations/test_detalhes.py reservations/views.py spaces/test_passo1.py \
    static/css/tailwind.css templates/reservations/reservation_form.html \
    templates/reservations/reservation_review.html \
    templates/spaces/_selection_summary.html \
    templates/spaces/_space_list_fragment.html templates/spaces/space_list.html

fase "Fase 15" \
"feat: escolha da faixa de horário já no passo de data" \
    reservations/availability.py reservations/test_availability.py spaces/views.py \
    static/css/tailwind.css templates/spaces/_availability.html

fase "Fase 16" \
"refactor: unifica os status da reserva num enum com rótulos e cores" \
    ai_assistant/tests.py assets/css/source.css core/tests.py reservations/enums.py \
    reservations/migrations/0005_alter_reservation_status.py reservations/tests.py \
    static/css/tailwind.css templates/base.html \
    templates/components/_reservation_status_badge.html

fase "Fase 17" \
"feat: agendador executa a liberação automática de reservas sem check-in" \
    admin_dashboard/forms.py core/tests.py docker-compose.prod.yml docker-compose.yml \
    pyproject.toml reservations/management/commands/agendador.py \
    reservations/management/commands/release_no_shows.py \
    reservations/migrations/0006_bookingpolicy_no_show_threshold_minutes_and_more.py \
    reservations/models.py reservations/services.py reservations/test_agendador.py \
    reservations/test_availability.py reservations/tests.py \
    templates/admin_dashboard/booking_policy_form.html uv.lock

fase "Fase 18" \
"feat: edição de assunto, participantes e serviços sem precisar remarcar" \
    config/urls.py reservations/services.py reservations/test_edicao.py \
    reservations/views.py services/services.py static/css/tailwind.css \
    templates/reservations/_service_picker.html \
    templates/reservations/reservation_detail.html \
    templates/reservations/reservation_details_edit.html

fase "Fase 18b" \
"test: ajusta os testes de integração ao fluxo com a tela de edição" \
    core/tests.py reservations/tests.py reservations/views.py spaces/tests.py

fase "Fase 19" \
"feat: calendário do usuário em mês, semana e dia" \
    config/urls.py core/tests.py reservations/calendario.py \
    reservations/test_calendario.py reservations/views.py templates/base_user.html \
    templates/reservations/_calendar_day.html \
    templates/reservations/_calendar_entry.html \
    templates/reservations/_calendar_month.html \
    templates/reservations/_calendar_week.html \
    templates/reservations/calendar.html \
    templates/reservations/reservation_detail.html

fase "Fase 19b" \
"feat: calendário geral da administração, com privacidade por não-busca" \
    admin_dashboard/test_calendario.py admin_dashboard/urls.py admin_dashboard/views.py \
    core/tests.py reservations/calendario.py \
    templates/admin_dashboard/_calendar_entry.html \
    templates/admin_dashboard/calendar.html templates/base_admin.html \
    templates/reservations/_calendar_day.html \
    templates/reservations/_calendar_month.html \
    templates/reservations/_calendar_week.html

fase "Fase 19c" \
"build: alvo make css e nota sobre o watcher do Tailwind sob WSL2" \
    AGENTS.md Makefile static/css/tailwind.css

fase "Fase 20" \
"feat: dias de funcionamento na política de reserva" \
    admin_dashboard/forms.py core/tests.py reservations/availability.py \
    reservations/calendario.py reservations/migrations/0007_dias_de_funcionamento.py \
    reservations/models.py reservations/test_availability.py \
    reservations/test_detalhes.py reservations/test_edicao.py \
    reservations/validators.py services/test_servicos.py \
    spaces/test_passo1.py spaces/test_passo2.py spaces/tests.py \
    static/css/tailwind.css templates/admin_dashboard/booking_policy_form.html \
    templates/base_admin.html templates/base_user.html \
    templates/reservations/_calendar_day.html \
    templates/reservations/_calendar_month.html

fase "Fase 21" \
"feat: registra a data do cancelamento da reserva" \
    reservations/migrations/0008_reservation_cancelled_at.py reservations/models.py \
    reservations/serializers.py reservations/services.py \
    reservations/test_cancelamento.py

fase "Fase 22a" \
"feat: cálculo dos relatórios de uso dos espaços" \
    reservations/relatorios.py reservations/test_relatorios.py

fase "Fase 22b" \
"feat: tela de relatórios com exportação em CSV" \
    admin_dashboard/test_relatorios.py admin_dashboard/views.py core/tests.py \
    static/css/tailwind.css templates/admin_dashboard/reports.html \
    templates/base_admin.html

fase "Fase 22c" \
"fix: registra as rotas de relatórios que faltaram no pacote anterior" \
    admin_dashboard/test_relatorios.py admin_dashboard/urls.py admin_dashboard/views.py \
    core/tests.py reservations/relatorios.py reservations/test_relatorios.py \
    templates/admin_dashboard/reports.html templates/base_admin.html

fase "Fase 23" \
"feat: tela de ajuda derivada da política, com blocos institucionais editáveis" \
    AGENTS.md README.md admin_dashboard/forms.py admin_dashboard/urls.py \
    admin_dashboard/views.py assets/css/source.css core/ajuda.py core/dashboard.py \
    core/migrations/0001_blocos_de_ajuda.py core/models.py core/test_ajuda.py \
    core/tests.py core/urls.py core/views.py reservations/steps.py \
    reservations/validators.py static/css/tailwind.css \
    templates/admin_dashboard/help_article_form.html \
    templates/admin_dashboard/help_article_list.html \
    templates/base_admin.html templates/base_user.html templates/core/ajuda.html

fase "Fase 24" \
"fix: contraste WCAG AA em toda a aplicação, com guarda automática" \
    AGENTS.md Makefile assets/css/source.css core/test_ajuda.py core/test_contraste.py \
    pyproject.toml reservations/steps.py reservations/test_steps.py \
    static/css/tailwind.css uv.lock \
    templates/accounts/login.html \
    templates/accounts/profile.html \
    templates/accounts/register.html \
    templates/admin_dashboard/_calendar_entry.html \
    templates/admin_dashboard/_occupancy_grid.html \
    templates/admin_dashboard/_reservation_row.html \
    templates/admin_dashboard/_reservation_table.html \
    templates/admin_dashboard/_space_status_badge.html \
    templates/admin_dashboard/_user_row.html \
    templates/admin_dashboard/attribute_form.html \
    templates/admin_dashboard/attribute_list.html \
    templates/admin_dashboard/booking_policy_form.html \
    templates/admin_dashboard/calendar.html \
    templates/admin_dashboard/index.html \
    templates/admin_dashboard/maintenance_form.html \
    templates/admin_dashboard/maintenance_list.html \
    templates/admin_dashboard/reports.html \
    templates/admin_dashboard/reservation_list.html \
    templates/admin_dashboard/service_queue.html \
    templates/admin_dashboard/service_type_form.html \
    templates/admin_dashboard/service_type_list.html \
    templates/admin_dashboard/space_form.html \
    templates/admin_dashboard/space_list.html \
    templates/admin_dashboard/space_type_form.html \
    templates/admin_dashboard/space_type_list.html \
    templates/admin_dashboard/user_form.html \
    templates/admin_dashboard/user_list.html \
    templates/base_admin.html \
    templates/base_user.html \
    templates/components/_reservation_status_badge.html \
    templates/components/_reservation_summary.html \
    templates/core/inicio.html \
    templates/knowledge/_assistant_answer.html \
    templates/knowledge/assistant.html \
    templates/partials/_availability_badge.html \
    templates/reservations/_calendar_day.html \
    templates/reservations/_calendar_entry.html \
    templates/reservations/_calendar_month.html \
    templates/reservations/_calendar_week.html \
    templates/reservations/_service_picker.html \
    templates/reservations/calendar.html \
    templates/reservations/reservation_detail.html \
    templates/reservations/reservation_details_edit.html \
    templates/reservations/reservation_form.html \
    templates/reservations/reservation_list.html \
    templates/reservations/reservation_reschedule.html \
    templates/reservations/reservation_review.html \
    templates/spaces/_alternativas.html \
    templates/spaces/_attribute_checkbox.html \
    templates/spaces/_availability.html \
    templates/spaces/_selection_summary.html \
    templates/spaces/_space_list_results.html \
    templates/spaces/space_detail.html \
    templates/spaces/space_list.html

# Tudo que não estiver em nenhum manifesto acima — inclusive os arquivos das
# Fases 1 e 2, cujos pacotes não existem mais.
fase "Restante" \
"chore: demais arquivos do redesign V2" \
    .

# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------
BASE="$(git rev-parse --short HEAD)"
BRANCH_ATUAL="$(git rev-parse --abbrev-ref HEAD)"

echo
echo "${NEGRITO}Plano${FIM}"
echo "  repositório .... $PWD"
echo "  base ........... $BASE ($BRANCH_ATUAL)"
if (( CRIAR_BRANCH )); then
    echo "  branch ......... ${VERDE}$BRANCH${FIM} (criada a partir da base)"
else
    echo "  branch ......... $BRANCH_ATUAL ${AMARELO}(commitando na branch atual)${FIM}"
fi
echo "  commits ........ até ${#NOMES[@]}, um por fase (fases sem mudança são puladas)"
echo "  hooks .......... ${AMARELO}--no-verify${FIM} (a suíte roda uma vez, no fim)"
if (( RODAR_TESTE )); then
    echo "  verificação .... '$COMANDO_TESTE' depois do último commit"
else
    echo "  verificação .... ${AMARELO}pulada${FIM}"
fi
echo
echo "  ${APAGADO}pendentes hoje: $(git status --porcelain -uall | wc -l) arquivos${FIM}"
echo

if (( DRY_RUN )); then
    echo "${AMARELO}--dry-run: nada será alterado.${FIM}"
    echo
fi

if (( CONFIRMAR )) && (( ! DRY_RUN )); then
    read -r -p "Prosseguir? [s/N] " resposta
    [[ "$resposta" =~ ^[sSyY]$ ]] || { echo "cancelado."; exit 0; }
    echo
fi

if (( CRIAR_BRANCH )) && (( ! DRY_RUN )); then
    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        erro "a branch '$BRANCH' já existe. Use --branch OUTRO_NOME ou --sem-branch"
    fi
    git checkout -b "$BRANCH"
    echo
fi

feitos=0
pulados=0

for i in "${!NOMES[@]}"; do
    nome="${NOMES[$i]}"
    mensagem="${MENSAGENS[$i]}"
    read -r -a caminhos <<< "${ARQUIVOS[$i]}"

    # Só passa adiante o que existe na árvore ou é conhecido do git. Um caminho
    # que não é nenhum dos dois faz o `git add` abortar o script inteiro.
    existentes=()
    for caminho in "${caminhos[@]}"; do
        if [[ -e "$caminho" ]] || git ls-files --error-unmatch -- "$caminho" >/dev/null 2>&1; then
            existentes+=("$caminho")
        fi
    done

    if (( ${#existentes[@]} == 0 )); then
        printf '  %-10s %s\n' "$nome" "${APAGADO}nenhum caminho presente — pulada${FIM}"
        (( pulados++ )) || true
        continue
    fi

    if (( DRY_RUN )); then
        # No ensaio o índice não pode ser tocado, então a estimativa vem do
        # diff da árvore contra o HEAD, limitado aos caminhos da fase.
        n=$(git status --porcelain -uall -- "${existentes[@]}" | wc -l | tr -d ' ')
        if (( n == 0 )); then
            printf '  %-10s %s\n' "$nome" "${APAGADO}sem mudanças — pulada${FIM}"
            (( pulados++ )) || true
        else
            printf '  %-10s %s%s%s  ~%s arquivo(s)\n' "$nome" "$VERDE" "$mensagem" "$FIM" "$n"
            (( feitos++ )) || true
        fi
        continue
    fi

    git add -A -- "${existentes[@]}"

    if git diff --cached --quiet; then
        printf '  %-10s %s\n' "$nome" "${APAGADO}sem mudanças — pulada${FIM}"
        (( pulados++ )) || true
        continue
    fi

    n=$(git diff --cached --name-only | wc -l | tr -d ' ')
    git commit --no-verify --quiet -m "$mensagem"
    printf '  %-10s %s%s%s  (%s arquivo(s), %s)\n' \
        "$nome" "$VERDE" "$mensagem" "$FIM" "$n" "$(git rev-parse --short HEAD)"
    (( feitos++ )) || true
done

echo
echo "${NEGRITO}Resultado${FIM}: $feitos commit(s), $pulados fase(s) sem mudança."

if (( DRY_RUN )); then
    echo "${AMARELO}Ensaio — nada foi alterado.${FIM}"
    exit 0
fi

restante="$(git status --porcelain || true)"
if [[ -n "$restante" ]]; then
    aviso "sobrou coisa fora dos commits (provavelmente arquivo ignorado ou fora da raiz):"
    echo "$restante" | sed 's/^/    /'
fi

echo
echo "${NEGRITO}Histórico criado${FIM}"
git --no-pager log --oneline "$BASE..HEAD" | sed 's/^/  /'

if (( RODAR_TESTE )); then
    echo
    echo "${NEGRITO}Verificação${FIM} — $COMANDO_TESTE"
    if $COMANDO_TESTE; then
        echo "${VERDE}Suíte verde sobre o estado final.${FIM}"
    else
        echo
        aviso "a suíte falhou. Os commits estão feitos e nada foi perdido — o"
        aviso "conteúdo dos arquivos é exatamente o que já estava na sua árvore."
        aviso "Para desfazer tudo e voltar ao ponto de partida:"
        if (( CRIAR_BRANCH )); then
            echo "    git checkout $BRANCH_ATUAL && git branch -D $BRANCH && git reset $BASE"
        else
            echo "    git reset $BASE"
        fi
        exit 1
    fi
fi

echo
echo "Para desfazer tudo e voltar ao ponto de partida, sem perder nenhuma alteração:"
if (( CRIAR_BRANCH )); then
    echo "    git checkout $BRANCH_ATUAL && git branch -D $BRANCH"
else
    echo "    git reset $BASE"
fi
