from sqlalchemy import Column, Integer, String, ForeignKey, Time, Date
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Profissional(Base):
    __tablename__ = 'profissionais'
    id = Column(Integer, primary_key=True)
    nome = Column(String, nullable=False)
    usuario = Column(String, nullable=False, unique=True)
    senha = Column(String, nullable=False)
    perfil = Column(String, nullable=False)


class Aluno(Base):
    __tablename__ = 'alunos'
    id = Column(Integer, primary_key=True)
    nome = Column(String)
    turno = Column(String)


class Agendamento(Base):
    __tablename__ = 'agendamentos'
    id = Column(Integer, primary_key=True)
    aluno_id = Column(Integer, ForeignKey('alunos.id'))
    profissional_id = Column(Integer, ForeignKey('profissionais.id'))
    data = Column(Date)
    hora = Column(Time)
    tipo = Column(String)
    status = Column(String)


class Disponibilidade(Base):
    __tablename__ = 'disponibilidades'
    id = Column(Integer, primary_key=True)
    profissional_id = Column(Integer, ForeignKey('profissionais.id'))
    data = Column(Date)
    dia_semana = Column(String)
    horario = Column(Time)


def listar_horarios_disponiveis(session, profissional_id, data_escolhida):
    dias = ['Segunda', 'Terça', 'Quarta',
            'Quinta', 'Sexta', 'Sábado', 'Domingo']
    dia_nome = dias[data_escolhida.weekday()]

    horarios_cadastrados = session.query(Disponibilidade).filter_by(
        profissional_id=profissional_id,
        data=data_escolhida,
        dia_semana=dia_nome,
    ).all()

    ocupados = session.query(Agendamento).filter_by(
        data=data_escolhida,
        profissional_id=profissional_id,
        status='Confirmado',
    ).all()
    horas_ocupadas = [agendamento.hora for agendamento in ocupados]

    return [disponibilidade.horario for disponibilidade in horarios_cadastrados if disponibilidade.horario not in horas_ocupadas]
