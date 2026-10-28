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
                descricao TEXT NOT NULL, 
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
# CRUD - Pessoas
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


def procurar_pessoa(pessoa_nome: str) -> dict | None:

    with closing(_conectar()) as conn:
        resposta = conn.execute(
            "SELECT id, nome FROM Pessoas WHERE nome = ?", 
            (pessoa_nome.strip(),)
        ).fetchone()
        
    return dict(resposta) if resposta else None


def listar_pessoas() -> list[dict]:

    with closing(_conectar()) as conn:

        resposta = [
            dict(r) 
            for r in conn.execute("SELECT * FROM Pessoas ORDER BY nome").fetchall()
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


#=======================================================================================================================
# CRUD - Recursos_de_Pagamento
#=======================================================================================================================

def criar_recurso_pagamento(
    pessoa_nome: str, 
    recurso: str, 
    tipo: str
) -> None:
    pessoa = procurar_pessoa(pessoa_nome.strip())

    if pessoa:
        with closing(_conectar()) as conn:
            conn.execute(
                "INSERT INTO Recursos_de_Pagamento (titular, recurso, tipo) VALUES (?, ?, ?)",
                (pessoa['id'], recurso.strip(), tipo.strip())
            )
            conn.commit()
            print(f"Recurso {recurso} cadastrado com sucesso para o titular {pessoa_nome}.") 
    else:
        print(f"pessoa {pessoa_nome} não está cadastrada!")



def listar_recursos_pagamento() -> list[dict]:

    with closing(_conectar()) as conn:
        query = """
            SELECT 
                rp.id,
                p.nome AS titular,
                rp.tipo,
                rp.recurso
            FROM Recursos_de_Pagamento rp
            JOIN Pessoas p ON rp.titular = p.id
        """

        resposta = [
            dict(r) 
            for r in conn.execute(query).fetchall()
        ]
    return resposta



def editar_recurso_pagamento(
    recurso_pagamento_id: int,
    recurso_pagamento_titular: str = None,
    recurso_pagamento_recurso: str = None,
    recurso_pagamento_tipo: str = None 
) -> bool:
    Campos_para_atualizar = []
    params = []

    if recurso_pagamento_titular != None:

        # Se o titular foi informado, valida e converte para ID
        pessoa = procurar_pessoa(recurso_pagamento_titular)
        if not pessoa:
            print(f"Titular {recurso_pagamento_titular} não cadastrado na tabela Pessoa.")
            return False

        Campos_para_atualizar.append("titular = ?")
        params.append(pessoa["id"])
    
    # Se o recurso foi informado, é acrescentado à lista de alterações 
    if recurso_pagamento_recurso != None:
        Campos_para_atualizar.append("recurso = ?")
        params.append(recurso_pagamento_recurso)

    # Se o tipo foi informado, ele será colocado na query para alteração de valor
    if recurso_pagamento_tipo != None:
        Campos_para_atualizar.append("tipo = ?")
        params.append(recurso_pagamento_tipo)

    # Se nenhum campo for informado, encerra-se a função
    if not Campos_para_atualizar:
        print("Nenhum campo foi fornecido para atualização.")
        return False

    # Adiciona o ID no final dos parâmetros (pra a cláusula WHERE)
    params.append(recurso_pagamento_id)

    # Criando a query para atualizar os campos modificados
    query = f"""
        UPDATE Recursos_de_Pagamento
        SET {", ".join(Campos_para_atualizar)}
        WHERE id = ?
    """

    with closing(_conectar()) as conn:
        conn.execute(query, tuple(params))
        conn.commit()

    return True



def deletar_recurso_pagamento(recurso_pagamento_id) -> bool:
    "Retorna True se deletou com sucesso ou False se houve impedimento por chave estrangeira"
    try:
        with closing(_conectar()) as conn:
            cursor = conn.execute(
                """
                    DELETE FROM Recursos_de_Pagamento
                    WHERE  id = ?
                """,
                (recurso_pagamento_id,)
            )
            conn.commit()
            return cursor.rowcount > 0

    except sqlite3.IntegrityError:
        print(f"Não é possivel deletar recurso_pagamento ID {recurso_pagamento_id}, pois ela possui registros vinculados.")
        return False



#=======================================================================================================================
# CRUD - Transacoes
#=======================================================================================================================

def criar_transacao(
    operador: str, 
    descricao: str,
    data: date, 
    valor: float, 
    tipo: str
) -> bool:
    # Verificar se o operador esta cadastrado na tabela Pessoa
    pessoa = procurar_pessoa(operador.strip())

    if pessoa:
        with closing(_conectar()) as conn:
            conn.execute(
                """
                    INSERT INTO Transacoes (operador,descricao, data, valor, tipo)
                    VALUES(?, ?, ?, ?, ?)
                """,
                (pessoa["id"],descricao.strip(), data.isoformat(), valor, tipo.strip()) #parametro tipo tem restrição (Receita e Despesa)
            )
            conn.commit()
            print(f"Transação {descricao} no valor de {valor}, cadastrado com sucesso.")

        return True
    else:
        print(f"Operador {operador} não cadastrado na Tabela Pessoas.")
        return False


def procurar_transacao(id: int) -> list | None:
    with closing(_conectar()) as conn:
        transacao = conn.execute("""
            SELECT * 
            FROM Transacoes
            WHERE id = ?
        """,
        (id,)        
        ).fetchone()
        return dict(transacao) if transacao else None

    
def listar_transacoes(
    operador: str | None = None,
    descricao: str | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    valor: float | None = None,
    tipo: str | None = None           
) -> list[dict]:
    adicionar_filtro = []
    params =[]

    # tratando a entrada operador
    if operador :
        pessoa = procurar_pessoa(operador.strip())

        if pessoa:
            adicionar_filtro.append("t.operador = ?")
            params.append(pessoa["id"])
        else: 
            print(f"Operador {operador.strip()} não está cadastrado na tabela Pessoas.")
            return []

    # Tratando entrada descricao
    if descricao:
        adicionar_filtro.append("t.descricao = ?")
        params.append(descricao)

    # Tratando entrada tipo
    if tipo:
        adicionar_filtro.append("t.tipo = ?")
        params.append(tipo)

    # Tratando as entradas de data
    if data_inicial and data_final:  
        if data_inicial != data_final:
            adicionar_filtro.append("t.data >= ?")
            params.append(data_inicial)

            adicionar_filtro.append("t.data <= ?")
            params.append(data_final)

        elif data_inicial == data_final:
            adicionar_filtro.append("t.data = ?")
            params.append(data_inicial)
    elif data_inicial:
        adicionar_filtro.append("t.data >= ?")
        params.append(data_inicial)
    elif data_final:
        adicionar_filtro.append("t.data <= ?")
        params.append(data_final)          

    # Tratando a entrada de valor
    if valor:
        adicionar_filtro.append("t.valor = ?")
        params.append(valor)

    # Caso nenhum filtro seja colocado
    #if not adicionar_filtro:
    #    print("Você não adicionou nenhum filtro.")
    #    return []

    #criando a conexão e a query de pesquisa
    with closing(_conectar()) as conn:

        if adicionar_filtro:
            respostas = conn.execute(f"""
                SELECT 
                    t.id,
                    p.nome AS operador,
                    t.descricao,
                    t.data,
                    t.valor,
                    t.tipo
                FROM Transacoes t
                JOIN Pessoas p ON t.operador = p.id
                WHERE {" AND ".join(adicionar_filtro)}
                ORDER BY t.data,
                    p.nome
            """,
            params,
        
            ).fetchall()
            return [dict(r) for r in respostas]
        else:
            respostas = conn.execute(f"""
                SELECT 
                    t.id,
                    p.nome AS operador,
                    t.descricao,
                    t.data,
                    t.valor,
                    t.tipo
                FROM Transacoes t
                JOIN Pessoas p ON t.operador = p.id
                ORDER BY t.data,
                    p.nome
            """).fetchall()
            return [dict(r) for r in respostas]


def editar_transacao(
    id: int,
    operador: str | None = None,
    descricao: str | None = None,
    data: date | None = None,
    valor: float | None = None,
    tipo: str | None = None     
 ) -> bool:

    # Verfica se a transação com o id informado existe no banco de dados
    transacao = procurar_transacao(id)
    campos_para_atualizar = []
    params = []

    if transacao:

        # tratar entrada operador 
        if operador: 
            pessoa = procurar_pessoa(operador.strip())   
            if not pessoa:
                print(f"O operador {operador.strip()} não esta cadastrado na tabela Pessoas!")
                return False

            campos_para_atualizar.append("operador = ?")
            params.append(pessoa["id"])

        # tratando entrada descrição
        if descricao:
            campos_para_atualizar.append("descricao = ?")
            params.append(descricao.strip())

        # tratando a entrada data
        if data:
            campos_para_atualizar.append("data = ?")
            params.append(data)

        # trantando a entrada valor
        if valor:
            campos_para_atualizar.append("valor = ?")
            params.append(valor)

        # tratando entrada tipo
        if tipo:
            campos_para_atualizar.append("tipo = ?")
            params.append(tipo.strip())

        # Adicionando o id da clasura WHERE da query
        params.append(id)

        # Criando a query
        query = f"""
            UPDATE Transacoes
            SET {", ".join(campos_para_atualizar)}
            WHERE id = ?
        """

        # Atualizando as colunas da transação definida
        with closing(_conectar()) as conn:
            conn.execute(query, tuple(params))
            conn.commit()
            return True
        

    else:
        print(f"Não existe transação com ID {id}!")
        return False
     

def deletar_transacao(id:int) -> bool:
    "Retorna True se deletou com sucesso ou False se houve impedimento por chave estrangeira"
    try:
        with closing(_conectar()) as conn:
            cursor = conn.execute("""
                DELETE FROM Transacoes 
                WHERE = ?
            """,
            (id,)

            )
            conn.commit() 
            return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        print(f"Não é possível deletar a transação de ID {id}, pois ela possui registros vinculados")
        return False



# Continuar construindo a funçao editar_transacao