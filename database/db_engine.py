from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from .models import Base

# Cria o arquivo do banco local
engine = create_engine('sqlite:///prepara_jovem.db')
Session = sessionmaker(bind=engine)


def init_db():
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if 'agendamentos' in existing_tables:
            agendamento_columns = {
                column['name'] for column in inspector.get_columns('agendamentos')}
            if 'profissional_id' not in agendamento_columns:
                connection.execute(
                    text('ALTER TABLE agendamentos ADD COLUMN profissional_id INTEGER'))

        if 'disponibilidades' in existing_tables:
            disponibilidade_columns = {
                column['name'] for column in inspector.get_columns('disponibilidades')}
            if 'profissional_id' not in disponibilidade_columns:
                connection.execute(
                    text('ALTER TABLE disponibilidades ADD COLUMN profissional_id INTEGER'))
            if 'data' not in disponibilidade_columns:
                connection.execute(
                    text('ALTER TABLE disponibilidades ADD COLUMN data DATE'))
