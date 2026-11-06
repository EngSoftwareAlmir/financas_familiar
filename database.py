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
) -> int | None :
    # Verificar se o operador esta cadastrado na tabela Pessoa
    pessoa = procurar_pessoa(operador.strip())

    if pessoa:
        with closing(_conectar()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                    INSERT INTO Transacoes (operador,descricao, data, valor, tipo)
                    VALUES(?, ?, ?, ?, ?)
                """,
                (pessoa["id"],descricao.strip(), data.isoformat(), valor, tipo.strip()) #parametro tipo tem restrição (Receita e Despesa)
            )
            conn.commit()

            # Captura o ID da transação criada
            transacao_id = cursor.lastrowid

            print(f"Transação {descricao} no valor de {valor}, cadastrado com sucesso.")    
            return transacao_id
    else:
        print(f"Operador {operador} não cadastrado na Tabela Pessoas.")
        return None


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
                WHERE id = ?
                """,
                (id,)

            )
            conn.commit() 
            return cursor.rowcount > 0
    except sqlite3.IntegrityError:
        print(f"Não é possível deletar a transação de ID {id}, pois ela possui registros vinculados")
        return False


#=======================================================================================================================
# CRUD - Receitas
#=======================================================================================================================
def criar_receita(
        data: date,
        operador: str,
        descricao: str,
        valor: float,
        recebido_em: str,
        frequencia: str,
        recorrencia: bool
) -> int | None:
    # Criando a transação ao qual ele correnponde
    id_transacao = criar_transacao(operador,descricao,data,valor, "Receita")

    if id_transacao:
        with closing(_conectar()) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                    INSERT INTO Receitas (transacao, frequencia, recebido_em, recorrencia)
                    VALUES (?, ?, ?, ?)
                """,
                (id_transacao, frequencia, recebido_em, recorrencia)            
            )
            conn.commit()
            
            print(f"Despesa vinculada a transacao de id {id_transacao} criada com sucesso.")
            # retorna o id da despesa criada
            return cursor.lastrowid
        
    else:        
        return None
    

def procurar_receita(id: int) -> dict | None:
    
    with closing(_conectar()) as conn:
        cursor = conn.cursor()
        resposta = cursor.execute("""
                SELECT 
                    r.id,
                    r.transacao,
                    t.data,
                    p.nome,
                    t.descricao,
                    t.valor,
                    r.recebido_em,
                    r.frequencia,
                    r.recorrencia                    
                FROM Receitas r
                JOIN Transacoes t ON transacao = t.id
                JOIN Pessoas p ON t.operador = p.id                    
                WHERE r.id = ?
            """,
            (id,)
        ).fetchone()
        return dict(resposta) if resposta else None
    

def editar_receita(
    id: int,
    data: date | None= None,
    operador: str | None= None,
    descricao: str| None= None,
    valor: float | None= None,
    recebido_em: str | None= None,
    frequencia: str | None= None,
    recorrencia: bool | None= None
) -> bool:
    #verficações
    # Verifica se a receita com o id informado existe
    receita = procurar_receita(id)    
    if not receita:
        print(f"Receita com ID {id} não existe. <Receitas>")
        return False
    
    # No caso do operador ser informado, verifica se ele esta cadastrado na tabela 'Pessoas'.
    pessoa: dict | None = None
    if operador is not None:
        pessoa = procurar_pessoa(operador)
        if pessoa is  None:
            print(f"O operador {operador} não está cadastrado na tabela de pessoas. <Receitas>")
            return False        

    atributos_receita = {          
        'recebido_em': recebido_em, 
        'frequencia': frequencia, 
        'recorrencia': recorrencia,        
    }

    atributos_transacao ={
        'id': receita["transacao"],
        'data' : data,
        'operador': operador, 
        'descricao': descricao,
        'valor': valor,
    }

    campos_atualizar_receita = [campo for campo, entrada in atributos_receita.items() if entrada is not None]
    params_receita = [atributos_receita[campo] for campo in campos_atualizar_receita]
    params_receita.append(id)
    campos_atualizar_receita_formatada = [f"{campo} = ?" for campo in campos_atualizar_receita]
    print(campos_atualizar_receita_formatada , " " , params_receita) # verficação

    query_receita = f"""
        UPDATE Receitas 
        SET {" , ".join(campos_atualizar_receita_formatada)}
        WHERE id = ?
    """    

    # atualizando atributos de receita
    with closing(_conectar()) as conn:
        cursor = conn.cursor()
        cursor.execute(query_receita, params_receita)
        conn.commit()

    #atualizando atributos de transação
    editar_transacao(**atributos_transacao)

    return True


def listar_receitas(
    # Parâmetros da tabela 'Transacoes'
    operador: str | None = None,
    descricao: str | None = None,
    data_inicial: date | None = None,
    data_final: date | None = None,
    valor: float | None = None,
    # Parâmetros da tabela 'Receitas'
    frequencia: str | None = None,
    recebido_em: str | None = None,
    recorrencia: bool | None = None,        
) -> list[dict]:
    
    """
    Descrição:
        Esta função retorna receita com base nos parâmetros inseridos ou todos os registros se nenhum parâmetro for 
        adicionado.

    Dependências:
        * _conectar()
        * procurar_pessoa()
    """

    # Caso o operador seja informado, verifica se ele esta cadastrado na tabela 'Pessoas'
    pessoa_id = None

    if operador is not None:
        pessoa= procurar_pessoa(operador)
        if pessoa:
            pessoa_id= pessoa["id"]            
            
        else:
            print(f"<Receitas>: O operador {operador} não esta cadastrado na tabela 'Pessoas'.")  
            return []

    parametros_pesquisa_receita = {
        'r.frequencia': frequencia,
        'r.recebido_em': recebido_em,
        'r.recorrencia': recorrencia
    }

    parametros_pesquisa_transacao = {
        't.operador': pessoa_id,
        't.descricao': descricao,
        't.valor': valor,
        't.tipo': 'Receita' # setado apenas para Receita, pois queremos só registros de receita
    }

    # Verificando os parâmetros de entrada da tabela Receitas e fazendo o seu tratamento
    filtros_receita = [campo for campo, entrada in parametros_pesquisa_receita.items() if entrada is not None]
    params_receita = [parametros_pesquisa_receita[campo] for campo in filtros_receita]
    filtros_receita_query = [f"{campo} = ?" for campo in filtros_receita]
   
    # Verificando os parâmetros de entrada da tabela Transacoes e fazendo o seu tratamento 
    filtros_transacao = [campo for campo, entrada in parametros_pesquisa_transacao.items() if entrada is not None]
    params_transacao = [parametros_pesquisa_transacao[campo] for campo in filtros_transacao] 
    filtros_transacao_query =[f"{campo} = ?" for campo in filtros_transacao]     
    
    # Unido todos os filtros e parâmetros de receita e transação
    todos_filtros = filtros_receita_query + filtros_transacao_query
    todos_params = params_receita + params_transacao

    # Tratando a entrada de datas e atualizando todos_filtros e todos_params
    if data_inicial and data_final:
        if data_inicial != data_final:
            todos_filtros.append("t.data >= ?")
            todos_filtros.append("t.data <= ?")
            todos_params.append(data_inicial)
            todos_params.append(data_final)
        else:
            todos_filtros.append("t.data = ?")
            todos_params.append(data_inicial)

    elif data_inicial:
        todos_filtros.append("t.data >= ?")
        todos_params.append(data_inicial)
    elif data_final:
        todos_filtros.append("t.data <= ?")
        todos_params.append(data_final)

    # Query para buscas
    query = f"""
        SELECT 
            r.id,
            r.transacao,
            t.data,
            p.nome,
            t.descricao,
            t.valor,
            r.recebido_em,
            r.frequencia,
            r.recorrencia
        FROM Receitas r
        JOIN Transacoes t ON r.transacao = t.id
        JOIN Pessoas p ON t.operador = p.id        
    """    

    if todos_filtros:
        query += " WHERE " + " AND ".join(todos_filtros)

    # Ordenar a pesquisa
    query += " ORDER BY t.data, p.nome"
    
    #realizando a consulta ao banco de dados
    with closing(_conectar()) as conn:
        cursor = conn.cursor()
        resposta = cursor.execute(query, todos_params).fetchall()

    return [dict(r) for r in resposta]


def deletar_receita(id: int) -> bool:
    """
    Descrição:
        Função que apaga do banco de dados um registro de receita especificada pelo ID, juntamente com a transação que está
        ligada a ela, uma vez que para cada receita há uma transação exclusiva e vice-versa.

    Dependências:
        * _conectar() 
        * procurar_receita()                  
    """

    # Verifica se existe algum registro com o Id informado, caso positivo armazena o id da transação ligada a ela.
    receita = procurar_receita(id)
    transacao_id: int = None
    if receita is not None:
       transacao_id = receita["transacao"]

    else:
        print(f"<Receitas>: Não existe receita com ID {id}.")
        return False

    query_deletar_receita = """
        DELETE FROM Receitas
        WHERE id = ?       
    """

    query_deletar_transacao = """
        DELETE FROM Transacoes
        WHERE id = ?
    """
    

    try: 
        with closing(_conectar()) as conn:
            cursor = conn.cursor()

            cursor.execute(query_deletar_receita, (id,)) 
            cursor.execute(query_deletar_transacao, (transacao_id,))
            conn.commit()

            return cursor.rowcount > 0
        
    except sqlite3.IntegrityError:
        print(f"<Receitas>: Não é possível deletar a receita ID {id}, pois ela possui registros vinculados.")

        return False
   