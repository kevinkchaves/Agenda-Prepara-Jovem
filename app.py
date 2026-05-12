import streamlit as st
from datetime import datetime, date, time, timedelta
from pathlib import Path

from database.db_engine import init_db, Session
from database.models import Aluno, Agendamento, Disponibilidade, Profissional, listar_horarios_disponiveis


DIA_SEMANA_NOMES = ["Segunda", "Terça", "Quarta",
                    "Quinta", "Sexta", "Sábado", "Domingo"]
BLOCOS_ATENDIMENTO = {
    "Manhã (08:00-12:00)": ("08:00", "11:30"),
    "Tarde (14:00-18:00)": ("13:00", "17:00"),
    "Noite (19:00-21:00)": ("17:30", "20:50"),
}
DIAS_PADRAO = ["Segunda", "Quarta", "Sexta"]
IMAGES_DIR = Path(__file__).parent / "images"


def gerar_slots_da_faixa(inicio_texto, fim_texto):
    horarios = []
    atual = datetime.strptime(inicio_texto, "%H:%M")
    fim = datetime.strptime(fim_texto, "%H:%M")

    while atual < fim:
        horarios.append(atual.time())
        atual += timedelta(minutes=20)

    return horarios


def listar_horarios_da_grade():
    horarios = []
    for inicio, fim in BLOCOS_ATENDIMENTO.values():
        horarios.extend(gerar_slots_da_faixa(inicio, fim))
    return horarios


def inicio_da_semana(data_base):
    return data_base - timedelta(days=data_base.weekday())


def fim_da_proxima_semana(data_base):
    inicio_proxima_semana = inicio_da_semana(data_base) + timedelta(days=7)
    return inicio_proxima_semana + timedelta(days=4)


def gerar_datas_da_semana(inicio_semana, dias_selecionados):
    datas = []
    for indice, nome_dia in enumerate(DIA_SEMANA_NOMES[:5]):
        if nome_dia in dias_selecionados:
            datas.append(inicio_semana + timedelta(days=indice))
    return datas


def formatar_data(data_objeto):
    return data_objeto.strftime("%d/%m/%y")


def obter_estado_slots_semana(session, profissional_id, inicio_semana, fim_semana):
    disponibilidades = session.query(Disponibilidade).filter(
        Disponibilidade.profissional_id == profissional_id,
        Disponibilidade.data >= inicio_semana,
        Disponibilidade.data <= fim_semana,
    ).all()

    agendamentos = session.query(Agendamento).filter(
        Agendamento.profissional_id == profissional_id,
        Agendamento.data >= inicio_semana,
        Agendamento.data <= fim_semana,
        Agendamento.status == "Confirmado",
    ).all()

    slots_disponiveis = {
        (item.data, item.horario)
        for item in disponibilidades
        if item.data and item.horario
    }
    slots_agendados = {
        (item.data, item.hora)
        for item in agendamentos
        if item.data and item.hora
    }

    return slots_disponiveis, slots_agendados


def alternar_disponibilidade_slot(session, profissional_id, data_agenda, horario):
    dia_semana = DIA_SEMANA_NOMES[data_agenda.weekday()]

    agendamento = session.query(Agendamento).filter_by(
        profissional_id=profissional_id,
        data=data_agenda,
        hora=horario,
        status="Confirmado",
    ).first()
    if agendamento:
        return False

    disponibilidade = session.query(Disponibilidade).filter_by(
        profissional_id=profissional_id,
        data=data_agenda,
        dia_semana=dia_semana,
        horario=horario,
    ).first()

    if disponibilidade:
        session.delete(disponibilidade)
    else:
        session.add(
            Disponibilidade(
                profissional_id=profissional_id,
                data=data_agenda,
                dia_semana=dia_semana,
                horario=horario,
            )
        )

    session.commit()
    return True


def bloquear_toda_semana(session, profissional_id, inicio_semana, fim_semana):
    # Remove todas as disponibilidades na semana (bloquear tudo)
    session.query(Disponibilidade).filter(
        Disponibilidade.profissional_id == profissional_id,
        Disponibilidade.data >= inicio_semana,
        Disponibilidade.data <= fim_semana,
    ).delete(synchronize_session=False)
    session.commit()


def desbloquear_toda_semana(session, profissional_id, inicio_semana, fim_semana):
    # Adiciona todas as disponibilidades padrão na semana (desbloquear tudo)
    horarios = listar_horarios_da_grade()
    for indice in range(5):
        data_agenda = inicio_semana + timedelta(days=indice)
        dia_semana = DIA_SEMANA_NOMES[indice]
        for horario in horarios:
            exists = session.query(Disponibilidade).filter_by(
                profissional_id=profissional_id,
                data=data_agenda,
                horario=horario,
            ).first()
            if not exists:
                session.add(
                    Disponibilidade(
                        profissional_id=profissional_id,
                        data=data_agenda,
                        dia_semana=dia_semana,
                        horario=horario,
                    )
                )
    session.commit()


def garantir_profissionais_padrao(session):
    profissionais_padrao = [
        {"nome": "Evelin", "usuario": "psicologa",
            "senha": "prepara123", "perfil": "Psicológico"},
        {"nome": "Joelma", "usuario": "pedagoga",
            "senha": "prepara123", "perfil": "Pedagógico"},
    ]

    profissionais_existentes = {
        profissional.usuario: profissional for profissional in session.query(Profissional).all()}
    criados = False

    for dados_profissional in profissionais_padrao:
        profissional_existente = profissionais_existentes.get(
            dados_profissional["usuario"])
        if profissional_existente is None:
            session.add(Profissional(**dados_profissional))
            criados = True
        elif profissional_existente.nome != dados_profissional["nome"]:
            profissional_existente.nome = dados_profissional["nome"]
            profissional_existente.perfil = dados_profissional["perfil"]
            criados = True

    if criados:
        session.commit()


def garantir_disponibilidade_padrao(session):
    if session.query(Disponibilidade).filter(Disponibilidade.data.isnot(None)).count() > 0:
        return

    horarios = listar_horarios_da_grade()
    profissionais = session.query(Profissional).all()
    hoje = date.today()
    semana_atual = inicio_da_semana(hoje)
    semana_seguinte = semana_atual + timedelta(days=7)

    for profissional in profissionais:
        for inicio_semana in [semana_atual, semana_seguinte]:
            for indice, dia_semana in enumerate(DIA_SEMANA_NOMES[:5]):
                if dia_semana not in DIAS_PADRAO:
                    continue

                data_agenda = inicio_semana + timedelta(days=indice)
                for horario in horarios:
                    session.add(
                        Disponibilidade(
                            profissional_id=profissional.id,
                            data=data_agenda,
                            dia_semana=dia_semana,
                            horario=horario,
                        )
                    )

    session.commit()


def normalizar_tipo_para_perfil(tipo_atendimento):
    return "Psicológico" if tipo_atendimento == "Psicológico" else "Pedagógico"


def obter_profissional_por_perfil(session, perfil):
    return session.query(Profissional).filter_by(perfil=perfil).order_by(Profissional.id).first()


def salvar_disponibilidade_profissional(session, profissional_id, dias_selecionados, blocos_selecionados):
    semana_inicio = inicio_da_semana(date.today())
    semana_fim = semana_inicio + timedelta(days=13)

    session.query(Disponibilidade).filter(
        Disponibilidade.profissional_id == profissional_id,
        Disponibilidade.data >= semana_inicio,
        Disponibilidade.data <= semana_fim,
    ).delete(synchronize_session=False)

    for data_agenda in gerar_datas_da_semana(semana_inicio, dias_selecionados):
        dia_semana = DIA_SEMANA_NOMES[data_agenda.weekday()]
        for bloco in blocos_selecionados:
            inicio, fim = BLOCOS_ATENDIMENTO[bloco]
            for horario in gerar_slots_da_faixa(inicio, fim):
                session.add(
                    Disponibilidade(
                        profissional_id=profissional_id,
                        data=data_agenda,
                        dia_semana=dia_semana,
                        horario=horario,
                    )
                )

    session.commit()


def salvar_disponibilidade_para_semana(session, profissional_id, inicio_semana, dias_selecionados, blocos_selecionados):
    semana_inicio = inicio_semana
    semana_fim = semana_inicio + timedelta(days=13)

    session.query(Disponibilidade).filter(
        Disponibilidade.profissional_id == profissional_id,
        Disponibilidade.data >= semana_inicio,
        Disponibilidade.data <= semana_fim,
    ).delete(synchronize_session=False)

    for data_agenda in gerar_datas_da_semana(semana_inicio, dias_selecionados):
        dia_semana = DIA_SEMANA_NOMES[data_agenda.weekday()]
        for bloco in blocos_selecionados:
            inicio, fim = BLOCOS_ATENDIMENTO[bloco]
            for horario in gerar_slots_da_faixa(inicio, fim):
                session.add(
                    Disponibilidade(
                        profissional_id=profissional_id,
                        data=data_agenda,
                        dia_semana=dia_semana,
                        horario=horario,
                    )
                )

    session.commit()


def backfill_agendamentos_existentes(session):
    agendamentos_sem_profissional = session.query(Agendamento).filter(
        Agendamento.profissional_id.is_(None)).all()

    for agendamento in agendamentos_sem_profissional:
        tipo = (agendamento.tipo or "").lower()
        if "psic" in tipo:
            perfil = "Psicológico"
        elif "pedag" in tipo:
            perfil = "Pedagógico"
        else:
            continue

        profissional = obter_profissional_por_perfil(session, perfil)
        if profissional:
            agendamento.profissional_id = profissional.id

    session.commit()


def datas_permitidas_para_agendamento():
    hoje = date.today()
    return hoje, fim_da_proxima_semana(hoje)


def formatar_periodo_semana(inicio_semana):
    fim_semana = inicio_semana + timedelta(days=4)
    return f"{formatar_data(inicio_semana)} a {formatar_data(fim_semana)}"


def bootstrap_database():
    session = Session()
    garantir_profissionais_padrao(session)
    garantir_disponibilidade_padrao(session)
    backfill_agendamentos_existentes(session)
    session.close()


def carregar_profissional_logado():
    profissional_id = st.session_state.get("profissional_id")
    if not profissional_id:
        return None

    session = Session()
    profissional = session.get(Profissional, profissional_id)
    session.close()
    return profissional


def deslogar_profissional():
    st.session_state.pop("profissional_id", None)
    st.session_state.pop("profissional_nome", None)
    st.session_state.pop("profissional_perfil", None)
    st.rerun()


def render_cabecalho_pagina(titulo, subtitulo, show_logo=False):
    """Renderiza cabeçalho com título e subtítulo usando st.columns para garantir que as imagens apareçam."""

    col_title, col_logo_center, col_logo_right = st.columns([2.8, 2, 2])

    with col_title:
        st.markdown(
            f"<h1 style='margin:0; font-size:2rem;'>{titulo}</h1>", unsafe_allow_html=True)
        st.markdown(
            f"<p style='margin:5px 0 0 0; font-size:0.95rem; color:#475569;'>{subtitulo}</p>", unsafe_allow_html=True)

    # Logo central: Prepara Jovem
    with col_logo_center:
        logo_prepara = IMAGES_DIR / "logo prepara.png"
        if logo_prepara.exists():
            st.image(str(logo_prepara), width=280)

    # Logo direita: Logo Simões Filho
    with col_logo_right:
        logo_simoes = IMAGES_DIR / "logo_simoesfilho.png"
        if logo_simoes.exists():
            st.image(str(logo_simoes), width=480)


def render_top_logos():
    """Renderiza os logos no topo da página quando presentes em `images/`.

    Procura por imagens contendo termos comuns e as exibe com destaque.
    """
    if not IMAGES_DIR.exists():
        return

    # possíveis nomes que o utilizador pode ter usado
    programa_names = [
        "logo_programa",
        "logo",
        "programa",
        "prepara",
        "logo_prepara",
    ]
    prefeitura_names = [
        "prefeitura",
        "municipio",
        "municipal",
        "logo_prefeitura",
    ]

    logo_programa = localizar_foto_profissional(programa_names)

    # Se não há logo do programa, nada a fazer
    if not logo_programa:
        return

    try:
        # Embed the image as base64 and render as fixed-position overlay
        import base64

        with open(logo_programa, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        html = f"""
        <div style="position:fixed; top:12px; right:12px; z-index:9999; pointer-events:none;">
            <img src="data:image/png;base64,{img_b64}" style="width:88px; height:auto; display:block; border-radius:8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);" />
        </div>
        """

        st.markdown(html, unsafe_allow_html=True)
    except Exception:
        # Fallback que tenta não afetar o layout principal
        try:
            c1, c2 = st.columns([9, 1])
            with c2:
                st.image(str(logo_programa), width=88)
        except Exception:
            pass


def localizar_foto_profissional(nomes_base):
    if not IMAGES_DIR.exists():
        return None

    nomes_lower = [n.lower() for n in nomes_base]
    for f in IMAGES_DIR.iterdir():
        if not f.is_file():
            continue
        stem = f.stem.lower()
        for nome in nomes_lower:
            if nome in stem or stem.startswith(nome):
                return f
    return None


def render_fotos_profissionais_sidebar():
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Profissionais")

    # If a professional is logged in, show only her photo
    profissional_id = st.session_state.get("profissional_id")
    if profissional_id:
        session = Session()
        prof = session.get(Profissional, profissional_id)
        session.close()
        if prof:
            # try several keys: usuario, nome, perfil
            keys = [getattr(prof, 'usuario', ''), getattr(
                prof, 'nome', ''), getattr(prof, 'perfil', '')]
            foto = localizar_foto_profissional(
                [k.lower().replace(' ', '_') for k in keys if k])
            if foto:
                def render_prof_photo(pathobj, caption):
                    try:
                        c1, c2, c3 = st.sidebar.columns([1, 2, 1])
                        c2.image(str(pathobj), caption=caption, width=100)
                    except Exception:
                        c1, c2, c3 = st.sidebar.columns([1, 2, 1])
                        c2.image(str(pathobj), caption=caption, width=100)

                render_prof_photo(foto, f"{prof.nome} - {prof.perfil}")
                return

    # default (no-one logged): show both known professionals if available
    evelin = localizar_foto_profissional(
        ["evelin", "psicóloga", "psicologa_evelin"])
    joelma = localizar_foto_profissional(
        ["joelma", "pedagoga", "pedagoga_joelma"])

    def render_prof_photo(pathobj, caption):
        try:
            c1, c2, c3 = st.sidebar.columns([1, 2, 1])
            c2.image(str(pathobj), caption=caption, width=100)
        except Exception:
            c1, c2, c3 = st.sidebar.columns([1, 2, 1])
            c2.image(str(pathobj), caption=caption, width=100)

    if evelin:
        render_prof_photo(evelin, "PSICÓLOGA")
    if joelma:
        render_prof_photo(joelma, "PEDAGOGA")

    if not evelin and not joelma:
        st.sidebar.caption(
            "Adicione fotos em images/: evelin.jpg e joelma.jpg")


init_db()
bootstrap_database()

st.set_page_config(
    page_title="Prepara Jovem - Agenda Semanal",
    page_icon=str(IMAGES_DIR / "logo prepara.png"),
    layout="wide",
)

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&display=swap');

        :root {
            --bg-soft: #f6fffd;
            --brand: #0f766e;
            --brand-soft: #14b8a6;
            --brand-strong: #134e4a;
            --card: #ffffff;
            --text: #0f172a;
            --muted: #475569;
            --border: #c7f0ea;
        }

        html, body, [class*="css"]  {
            font-family: 'Poppins', 'Segoe UI', sans-serif;
            color: var(--text);
        }

        .stApp {
            background: #f7faf9;
        }

        .page-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            padding: 8px 4px 14px 4px;
            border-bottom: 1px solid #d8efeb;
            margin-bottom: 18px;
            position: relative; /* necessário para posicionar o logo central absoluto */
        }

        .page-title {
            margin: 0;
            font-size: 1.8rem;
            color: #0f172a;
            font-weight: 700;
        }

        .page-header img {
            max-height: 160px;
            max-width: 100%;
            height: auto;
            object-fit: contain;
            display: block;
            margin: 0;
            vertical-align: middle; /* alinha com o texto */
            filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.05));
        }

        /* Logo central travado no meio exato */
        .logo-center {
            position: absolute;
            left: 50%;
            transform: translateX(-50%);
            pointer-events: none; /* evita interação */
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .page-header .page-title {
            font-size: 2rem;
            margin: 0;
        }

        .page-subtitle {
            margin: 5px 0 0 0;
            font-size: 0.95rem;
            color: #475569;
        }

        /* Responsividade: empilha em telas pequenas */
        @media (max-width: 720px) {
            .page-header {
                flex-direction: column;
                align-items: center;
                text-align: center;
            }

            .page-header img {
                max-height: 120px;
                margin-top: 8px;
            }
        }

        .stForm {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 18px;
            box-shadow: 0 8px 24px rgba(20, 184, 166, 0.08);
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 10px;
            background: #eafdf9;
            padding: 8px;
            border-radius: 14px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 10px;
            font-weight: 600;
            color: #0f766e;
            border: 1px solid #ccfbf1;
            background: #f8fffd;
        }

        .stTabs [aria-selected="true"] {
            background: #0f766e !important;
            color: #ffffff !important;
            border-color: #0f766e !important;
        }

        .stButton button, .stFormSubmitButton button {
            border-radius: 10px;
            border: 1px solid #0f766e;
            background: #0f766e;
            color: #ffffff;
            font-weight: 600;
            padding: 0.45rem 0.9rem;
        }

        .stButton button[kind="primary"] {
            border-color: #6fbf8f !important;
            background: #6fbf8f !important;
            color: #ffffff !important;
        }

        .stButton button[kind="primary"]:hover {
            border-color: #5ca87c !important;
            background: #5ca87c !important;
            color: #ffffff !important;
        }

        .stButton button[kind="secondary"] {
            border-color: #d1d5db !important;
            background: #f3f4f6 !important;
            color: #4b5563 !important;
        }

        .stButton button[kind="secondary"]:hover {
            border-color: #bfc7d5 !important;
            background: #e5e7eb !important;
            color: #374151 !important;
        }

        .stButton button:disabled {
            border-color: #f1a6a6 !important;
            background: #f8d7da !important;
            color: #a11b2b !important;
            opacity: 1 !important;
            cursor: not-allowed !important;
        }

        .stButton button:hover, .stFormSubmitButton button:hover {
            border-color: #0d5f59;
            background: #115e59;
            color: #ffffff;
        }

        .stAlert {
            border-radius: 12px;
        }

        /* Professional photo styling */
        /* professional photos use Streamlit image rendering (no extra CSS) */
    </style>
    """,
    unsafe_allow_html=True,
)

# top overlay removed; logo will be shown inline beside the Agendar header

menu = st.sidebar.selectbox(
    "Menu", ["Agendar Atendimento", "Área Profissional"])
# professional photos are rendered after sidebar login box (see bottom of file)

if menu == "Agendar Atendimento":
    render_cabecalho_pagina(
        "Agende Seu Atendimento", "Escolha o tipo de atendimento, data e horário disponíveis.", show_logo=True)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.subheader("Solicite seu horário")

        # Esconder a instrução padrão "Press Enter to submit form"
        st.markdown("""
        <style>
            [data-testid="InputInstructions"] {
                display: none !important;
            }
        </style>
        """, unsafe_allow_html=True)

        # Inicializar flag para controlar exibição do aviso
        if "mostrar_aviso_vagas" not in st.session_state:
            st.session_state.mostrar_aviso_vagas = False

        with st.form("form_agendamento"):
            nome = st.text_input(
                "Nome Completo", placeholder="Digite seu nome completo...")
            turno = st.selectbox(
                "Seu Turno", ["Matutino", "Vespertino", "Noturno"])
            tipo = st.selectbox("Tipo de Atendimento", [
                                "Psicológico", "Pedagógico"])

            # Obter a profissional baseado no tipo de atendimento
            session = Session()
            perfil = normalizar_tipo_para_perfil(tipo)
            profissional = obter_profissional_por_perfil(session, perfil)

            # Listar apenas datas com horários disponíveis
            data_minima, data_maxima = datas_permitidas_para_agendamento()
            datas_disponiveis = []

            if profissional:
                data_atual = data_minima + timedelta(days=1)
                while data_atual <= data_maxima:
                    horarios_dia = listar_horarios_disponiveis(
                        session, profissional.id, data_atual)
                    if horarios_dia:
                        datas_disponiveis.append(data_atual)
                    data_atual += timedelta(days=1)

            session.close()

            if datas_disponiveis:
                data_escolhida = st.selectbox(
                    "Escolha a Data",
                    datas_disponiveis,
                    format_func=lambda x: f"{x.strftime('%d/%m/%Y')} ({DIA_SEMANA_NOMES[x.weekday()]})"
                )

                session = Session()
                horarios = listar_horarios_disponiveis(
                    session, profissional.id, data_escolhida)
                session.close()

                if horarios:
                    h_sel = st.selectbox(
                        "Horários Disponíveis", horarios, format_func=lambda x: x.strftime("%H:%M"))
                    enviar = st.form_submit_button("Confirmar Agendamento")
                    st.session_state.mostrar_aviso_vagas = False
                else:
                    h_sel = None
                    enviar = st.form_submit_button("Confirmar Agendamento")
            else:
                st.warning("Não há datas com vagas disponíveis no período.")
                h_sel = None
                enviar = st.form_submit_button(
                    "Confirmar Agendamento", disabled=True)

            if enviar and nome and horarios and profissional:
                session = Session()
                novo_aluno = Aluno(nome=nome, turno=turno)
                session.add(novo_aluno)
                session.flush()

                novo_agendamento = Agendamento(
                    aluno_id=novo_aluno.id,
                    profissional_id=profissional.id,
                    data=data_escolhida,
                    hora=h_sel,
                    tipo=tipo,
                    status="Confirmado",
                )
                session.add(novo_agendamento)
                session.commit()
                session.close()
                st.success("Agendamento confirmado!")

elif menu == "Área Profissional":
    render_cabecalho_pagina(
        "Painel Profissional",
        "Controle semanal, bloqueios e programação da agenda.",
    )

    profissional_logada = carregar_profissional_logado()

    if profissional_logada is None:
        # Esconder a instrução padrão "Press Enter to submit form"
        st.markdown("""
        <style>
            [data-testid="InputInstructions"] {
                display: none !important;
            }
        </style>
        """, unsafe_allow_html=True)

        with st.sidebar.form("login_profissional"):
            usuario = st.text_input(
                "Usuário", placeholder="Digite o nome do usuário...")
            senha = st.text_input("Senha", type="password",
                                  placeholder="Digite sua senha...")
            entrar = st.form_submit_button("Entrar")

        if entrar:
            session = Session()
            profissional = session.query(Profissional).filter_by(
                usuario=usuario.strip(), senha=senha).first()
            session.close()

            if profissional:
                st.session_state["profissional_id"] = profissional.id
                st.session_state["profissional_nome"] = profissional.nome
                st.session_state["profissional_perfil"] = profissional.perfil
                st.rerun()
            else:
                st.sidebar.error("Usuário ou senha inválidos.")

        st.info(
            "Use o login da profissional para acessar a agenda e a configuração de disponibilidade.")

    else:
        st.sidebar.success(f"Logado como {profissional_logada.nome}")
        if st.sidebar.button("Sair"):
            deslogar_profissional()

        tab_agenda, tab_config = st.tabs(
            ["📅 Agenda Semanal", "⚙️ Configurar Dias"])

        with tab_agenda:
            session = Session()
            profissional = session.get(
                Profissional, st.session_state["profissional_id"])

            if not profissional:
                session.close()
                st.error("Profissional não encontrada no banco.")

            else:
                data_minima, data_maxima = datas_permitidas_para_agendamento()
                data_referencia = st.date_input(
                    "Ver semana a partir de:",
                    value=date.today(),
                    min_value=data_minima,
                    max_value=data_maxima,
                    format="DD/MM/YYYY",
                )
                inicio_semana = inicio_da_semana(data_referencia)
                fim_semana = inicio_semana + timedelta(days=4)
                disponibilidades_semana = session.query(Disponibilidade).filter(
                    Disponibilidade.profissional_id == profissional.id,
                    Disponibilidade.data >= inicio_semana,
                    Disponibilidade.data <= fim_semana,
                ).all()

                dias_com_configuracao = sorted({
                    item.data for item in disponibilidades_semana if item.data
                })
                agendamentos_semana = session.query(Agendamento).filter(
                    Agendamento.profissional_id == profissional.id,
                    Agendamento.data >= inicio_semana,
                    Agendamento.data <= fim_semana,
                    Agendamento.status == "Confirmado",
                ).count()

                st.markdown(
                    f"### Semana de {formatar_periodo_semana(inicio_semana)}")

                resumo_col1, resumo_col2, resumo_col3 = st.columns(3)
                with resumo_col1:
                    st.metric("Profissional", profissional.nome)
                with resumo_col2:
                    st.markdown(
                        f"<div style='padding: 16px; border-radius: 12px; background: #f7f8fb; border: 1px solid #e8eaf0;'>"
                        f"<div style='font-size: 0.85rem; color: #667085;'>Atendimento</div>"
                        f"<div style='font-size: 1.1rem; font-weight: 700;'>{profissional.perfil}</div>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with resumo_col3:
                    st.metric("Agendamentos na semana", agendamentos_semana)

                st.caption(
                    "Use o seletor acima para navegar pela semana permitida. A grade mostra apenas os dias com disponibilidade salva."
                )

                datas_atendimento = dias_com_configuracao

                if not datas_atendimento:
                    st.info(
                        "Nenhuma disponibilidade cadastrada para esta profissional.")

                colunas_dias = st.columns(5)
                horarios_grade = listar_horarios_da_grade()

                for indice, coluna in enumerate(colunas_dias):
                    dia_atual = inicio_semana + timedelta(days=indice)
                    nome_dia = DIA_SEMANA_NOMES[indice]

                    with coluna:
                        st.markdown(
                            f"<div style='padding: 10px 12px; border-radius: 14px; background: #f7f8fb; border: 1px solid #e8eaf0; margin-bottom: 10px;'>"
                            f"<strong>{nome_dia}</strong><br><span style='color:#667085'>{formatar_data(dia_atual)}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                        if dia_atual not in datas_atendimento:
                            st.caption("Sem agendamento individual")
                            continue

                        for horario in horarios_grade:
                            agendamento = (
                                session.query(Agendamento)
                                .filter_by(
                                    data=dia_atual,
                                    hora=horario,
                                    profissional_id=profissional.id,
                                    status="Confirmado",
                                )
                                .first()
                            )

                            if agendamento:
                                aluno = session.get(
                                    Aluno, agendamento.aluno_id)
                                nome_aluno = aluno.nome if aluno else "Aluno removido"
                                if st.button(
                                    f"🔴 {horario.strftime('%H:%M')}",
                                    key=f"{dia_atual.isoformat()}-{horario.strftime('%H%M')}",
                                ):
                                    detalhe_turno = aluno.turno if aluno else "Turno indisponível"
                                    st.toast(
                                        f"Paciente: {nome_aluno} ({detalhe_turno})")
                            else:
                                st.caption(f"🟢 {horario.strftime('%H:%M')}")

                session.close()

        with tab_config:
            st.markdown("### Programe a sua semana")
            st.caption(
                "Aqui você escolhe como a semana vai funcionar para a profissional logada. A configuração salva substitui apenas a semana selecionada.")

            session = Session()
            profissional = session.get(
                Profissional, st.session_state["profissional_id"])

            data_minima, data_maxima = datas_permitidas_para_agendamento()
            painel_col1, painel_col2 = st.columns([1.4, 1])

            with painel_col1:
                semana_referencia = st.date_input(
                    "Semana a programar:",
                    value=date.today(),
                    min_value=data_minima,
                    max_value=data_maxima,
                    format="DD/MM/YYYY",
                )
            inicio_semana = inicio_da_semana(semana_referencia)
            fim_semana = inicio_semana + timedelta(days=4)

            with painel_col2:
                st.markdown(
                    f"<div style='padding: 14px; border-radius: 16px; background: linear-gradient(135deg, #eef4ff, #f8faff); border: 1px solid #d9e4ff;'>"
                    f"<div style='font-size: 0.9rem; color: #4f6fad;'>Semana selecionada</div>"
                    f"<div style='font-size: 1.1rem; font-weight: 700;'>{formatar_periodo_semana(inicio_semana)}</div>"
                    f"<div style='font-size: 0.9rem; color: #4b5563; margin-top: 6px;'>Essa configuração vale para a profissional logada.</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.divider()

            if profissional:
                # Botões para bloquear/desbloquear toda a semana
                acao_col1, acao_col2 = st.columns([1, 1])
                with acao_col1:
                    if st.button("Bloquear tudo (esta semana)"):
                        bloquear_toda_semana(
                            session, profissional.id, inicio_semana, fim_semana)
                        st.success(
                            "Todos os horários desta semana foram bloqueados.")
                        st.rerun()
                with acao_col2:
                    if st.button("Desbloquear tudo (esta semana)"):
                        desbloquear_toda_semana(
                            session, profissional.id, inicio_semana, fim_semana)
                        st.success(
                            "Todos os horários desta semana foram disponibilizados.")
                        st.rerun()

                st.divider()

                # Painel: escolha os dias da semana com disponibilidade e os blocos a aplicar
                dispon_semana = session.query(Disponibilidade).filter(
                    Disponibilidade.profissional_id == profissional.id,
                    Disponibilidade.data >= inicio_semana,
                    Disponibilidade.data <= fim_semana,
                ).all()
                dias_existentes = {
                    DIA_SEMANA_NOMES[item.data.weekday()] for item in dispon_semana if item.data}

                # Dias da semana selecionados por padrão (segunda a sexta)
                dias_selecionados = DIA_SEMANA_NOMES[:5]

                # Blocos de atendimento selecionados por padrão (todos)
                blocos = list(BLOCOS_ATENDIMENTO.keys())
                blocos_selecionados = blocos

                st.caption(
                    "Use a grade abaixo para ajustes pontuais por horário.")

                slots_disponiveis, slots_agendados = obter_estado_slots_semana(
                    session,
                    profissional.id,
                    inicio_semana,
                    fim_semana,
                )

                colunas_dias = st.columns(5)
                horarios_grade = listar_horarios_da_grade()

                for indice, coluna in enumerate(colunas_dias):
                    dia_atual = inicio_semana + timedelta(days=indice)
                    nome_dia = DIA_SEMANA_NOMES[indice]

                    with coluna:
                        st.markdown(
                            f"<div style='padding: 10px 12px; border-radius: 14px; background: #f7f8fb; border: 1px solid #e8eaf0; margin-bottom: 10px;'>"
                            f"<strong>{nome_dia}</strong><br><span style='color:#667085'>{formatar_data(dia_atual)}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

                        for horario in horarios_grade:
                            chave_slot = (dia_atual, horario)

                            if chave_slot in slots_agendados:
                                aluno_agendado = session.query(Agendamento).filter_by(
                                    profissional_id=profissional.id,
                                    data=dia_atual,
                                    hora=horario,
                                    status="Confirmado",
                                ).first()
                                aluno = session.get(
                                    Aluno, aluno_agendado.aluno_id) if aluno_agendado else None
                                nome_aluno = aluno.nome if aluno else "Agendado"
                                st.button(
                                    f"🔒 {horario.strftime('%H:%M')}",
                                    key=f"bloqueado-{dia_atual.isoformat()}-{horario.strftime('%H%M')}",
                                    disabled=True,
                                    type="secondary",
                                    use_container_width=True,
                                )
                                continue

                            esta_disponivel = chave_slot in slots_disponiveis
                            botao_label = (
                                f"🟢 {horario.strftime('%H:%M')}"
                                if esta_disponivel
                                else f"⚪ {horario.strftime('%H:%M')}"
                            )
                            botao_ajuda = (
                                "Clique para bloquear este horário"
                                if esta_disponivel
                                else "Clique para disponibilizar este horário"
                            )

                            if st.button(
                                botao_label,
                                key=f"toggle-{dia_atual.isoformat()}-{horario.strftime('%H%M')}",
                                type="secondary",
                                use_container_width=True,
                            ):
                                if alternar_disponibilidade_slot(session, profissional.id, dia_atual, horario):
                                    st.rerun()
                                else:
                                    st.warning(
                                        "Este horário já possui agendamento e não pode ser alterado.")

                session.close()
            else:
                session.close()
                st.error("Profissional não encontrada no banco.")

# Render professional photos in sidebar after page setup so they appear below login box
render_fotos_profissionais_sidebar()
