import sqlite3
from contextlib import closing
from datetime import date
from pathlib import Path

# Criando/setando um banco de dados
DB_PATH = Path(__file__).parent /"banco_de_dados.db"

#===============================================================================
# CONEXÃO COM BANCO DE DADOS
#===============================================================================
def _conectar() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)

    #----Configurações----------------------------------------------------------

    # Faz com que cada linha retornada pelo banco seja um dicionário e não uma array;
    conn.row_factory = sqlite3.Row
    # Para o sqlite não ignorar as retriçoes de chave estrangeira
    conn.execute("PRAGMA foreign_keys = ON")

    return conn


#===============================================================================
# CRIAÇÃO DO BANCO DE DADOS
#===============================================================================

def inicializar_banco() -> None:
    # O 'closing' garante o conn.close e o 'with' garante a transação
    with closing(_conectar()) as conn:

        # Criando as tabelas do banco de dados
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS Pessoas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Recursos_de_Pagamento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titular INTEGER NOT NULL REFERENCES Pessoas(id),
                recurso TEXT NOT NULL, 
                tipo TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS Transacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operador INTEGER NOT NULL REFERENCES Pessoas(id),
                data DATE NOT NULL,
                valor REAL NOT NULL CHECK(valor > 0),
                tipo TEXT NOT NULL CHECK(tipo IN ('Receita', 'Despesa'))
            );

            CREATE TABLE IF NOT EXISTS Despesas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transacao INTEGER NOT NULL REFERENCES Transacoes(id),
                forma_pagamento INTEGER NOT NULL REFERENCES Recursos_de_Pagamento(id),
                tipo TEXT NOT NULL DEFAULT 'à vista' CHECK(tipo IN ('à vista', 'financiada')),
                total_parcelas INTEGER NOT NULL DEFAULT 1 CHECK(total_parcelas > 0),
                parcelas_pagas INTEGER NOT NULL DEFAULT 1 CHECK(parcelas_pagas >= 0 And parcelas_pagas <= total_parcelas),
                quitado INTEGER NOT NULL DEFAULT 1 CHECK(quitado IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS Receitas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transacao INTEGER NOT NULL REFERENCES Transacoes(id),
                frequencia TEXT NOT NULL DEFAULT 'recorrente' CHECK(frequencia IN ('recorrente', 'extra', 'pontual')),
                recebido_em TEXT NOT NULL,
                recorrencia INTEGER NOT NULL DEFAULT 0 CHECK(recorrencia IN (0,1))
            );
            """)  


#======================================================================================================================
# CRUD - PESSOAS
#======================================================================================================================
         
def criar_pessoa(
    nome: str
) -> None:
    
    with closing(_conectar()) as conn:
        conn.execute(
            "INSERT INTO Pessoas (nome) VALUES (?)",
            (nome.strip(),)
        )
        conn.commit()

def listar_pessoas() -> list[dict]:

    with closing(_conectar()) as conn:

        resposta = [
            dict(r) 
            for r in conn.execute("SELECT * FROM Pessoas").fetchall()
        ]

    return resposta


def editar_pessoa(pessoa_id: int, novo_nome: str ) -> None:
    with closing(_conectar()) as conn:
        conn.execute(
            "UPDATE Pessoas SET nome = ? WHERE id = ?",
            (novo_nome, pessoa_id),
        )
        conn.commit()


def deletar_pessoa(pessoa_id: int) -> bool :
    "Retorna True se deletou com sucesso ou False se houver impedimento por chave estrangeira"
    try:         
        with closing(_conectar()) as conn:
            cursor = conn.execute(
                "DELETE FROM Pessoas WHERE id = ?",
                (pessoa_id,)
            )
            conn.commit() # necessário para salvar a remoção no arquivo .db
            
            # Retorna True se algum registro foi realmente afetado/deletado
            return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        print(f"Não é possível deletar a pessoa ID {pessoa_id} pois ela possui registros vinculados.")
        return False
    