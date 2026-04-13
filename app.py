import os
from flask import Flask, request, render_template_string
import oracledb

app = Flask(__name__)

USUARIO_ORACLE = os.getenv("USUARIO_ORACLE")
SENHA_ORACLE = os.getenv("SENHA_ORACLE")
HOST_ORACLE = os.getenv("HOST_ORACLE", "oracle.fiap.com.br")
PORTA_ORACLE = os.getenv("PORTA_ORACLE", "1521")
SERVICE_NAME_ORACLE = os.getenv("SERVICE_NAME_ORACLE", "ORCL")


def conectar_oracle():
    dsn = f"{HOST_ORACLE}:{PORTA_ORACLE}/{SERVICE_NAME_ORACLE}"
    return oracledb.connect(
        user=USUARIO_ORACLE,
        password=SENHA_ORACLE,
        dsn=dsn
    )


def buscar_participantes():
    conn = None
    cursor = None
    try:
        conn = conectar_oracle()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                i.ID_INSCRICAO,
                u.NOME,
                u.PRIORIDADE,
                i.STATUS,
                i.WAITLIST,
                TO_CHAR(i.DATA_INSCRICAO, 'DD/MM/YYYY') AS DATA_INSCRICAO
            FROM INSCRICOES i
            JOIN USUARIOS u ON u.ID_USUARIO = i.ID_USUARIO
            ORDER BY
                CASE WHEN i.WAITLIST = 'SIM' THEN 0 ELSE 1 END,
                u.PRIORIDADE DESC,
                i.DATA_INSCRICAO ASC
        """)

        dados = cursor.fetchall()

        participantes = []
        for row in dados:
            prioridade_num = row[2]

            if prioridade_num == 3:
                prioridade_texto = "3 - Platinum"
            elif prioridade_num == 2:
                prioridade_texto = "2 - VIP"
            else:
                prioridade_texto = "1 - Normal"

            participantes.append({
                "id_inscricao": row[0],
                "nome": row[1],
                "prioridade": prioridade_texto,
                "status": row[3],
                "waitlist": row[4],
                "data_inscricao": row[5],
            })

        return participantes, None

    except Exception as e:
        return [], str(e)

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def executar_bloco(vagas_liberar):
    conn = None
    cursor = None

    try:
        conn = conectar_oracle()
        cursor = conn.cursor()

        out_msg = cursor.var(oracledb.DB_TYPE_VARCHAR, size=4000)
        out_qtd = cursor.var(oracledb.DB_TYPE_NUMBER)

        plsql_block = """
        DECLARE
            CURSOR c_waitlist IS
                SELECT I.ID_INSCRICAO, I.STATUS, I.WAITLIST, I.DATA_INSCRICAO,
                       U.NOME, U.PRIORIDADE
                FROM INSCRICOES I
                JOIN USUARIOS U ON U.ID_USUARIO = I.ID_USUARIO
                WHERE I.WAITLIST = 'SIM'
                ORDER BY U.PRIORIDADE DESC, I.DATA_INSCRICAO ASC
                FOR UPDATE OF I.STATUS;

            v_registro c_waitlist%ROWTYPE;
            v_promovidos NUMBER := 0;
            v_limite NUMBER := :p_vagas;

        BEGIN
            IF v_limite <= 0 THEN
                RAISE_APPLICATION_ERROR(-20001, 'A quantidade de vagas deve ser maior que zero.');
            END IF;

            OPEN c_waitlist;
            LOOP
                FETCH c_waitlist INTO v_registro;
                EXIT WHEN c_waitlist%NOTFOUND OR v_promovidos >= v_limite;

                UPDATE INSCRICOES
                SET STATUS = 'ATIVO',
                    WAITLIST = 'NAO'
                WHERE CURRENT OF c_waitlist;

                INSERT INTO HISTORICO_STATUS (
                    ID_HISTORICO,
                    ID_INSCRICAO,
                    STATUS_ANTERIOR,
                    STATUS_NOVO,
                    DT_ALTERACAO
                ) VALUES (
                    SEQ_HISTORICO_STATUS.NEXTVAL,
                    v_registro.ID_INSCRICAO,
                    v_registro.STATUS,
                    'ATIVO',
                    SYSDATE
                );

                v_promovidos := v_promovidos + 1;
            END LOOP;

            CLOSE c_waitlist;

            :p_qtd := v_promovidos;

            IF v_promovidos = 0 THEN
                :p_msg := 'Nenhum participante disponível na fila de espera para promoção.';
            ELSE
                :p_msg := 'Processo executado com sucesso. Promovidos: ' || v_promovidos;
            END IF;

        EXCEPTION
            WHEN OTHERS THEN
                :p_qtd := 0;
                :p_msg := 'Erro Oracle: ' || SQLERRM;
                RAISE;
        END;
        """

        cursor.execute(
            plsql_block,
            p_vagas=int(vagas_liberar),
            p_qtd=out_qtd,
            p_msg=out_msg
        )

        conn.commit()

        return {"sucesso": True, "mensagem": out_msg.getvalue() or ""}

    except oracledb.DatabaseError as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        erro, = e.args
        return {"sucesso": False, "erro": f"Oracle-{erro.code}: {erro.message}"}

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        return {"sucesso": False, "erro": str(e)}

    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass


HTML = """
<!DOCTYPE html>
<html lang="pt-br">
<head>
    <meta charset="UTF-8">
    <title>The Grand Tech Gala</title>
    <style>
        * {
            box-sizing: border-box;
        }

        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 40px;
            background: linear-gradient(135deg, #111111, #1b1b1f, #222228);
            color: #f5f5f5;
        }

        .container {
            max-width: 1100px;
            margin: 0 auto;
        }

        h1 {
            color: #ff0f68;
            font-size: 52px;
            margin-bottom: 8px;
        }

        h2 {
            color: #d7d7d7;
            font-size: 22px;
            font-weight: normal;
            margin-bottom: 30px;
        }

        .box {
            background: rgba(18, 18, 20, 0.96);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 24px;
            padding: 28px;
            margin-bottom: 24px;
            box-shadow: 0 8px 28px rgba(0, 0, 0, 0.28);
        }

        .box h3 {
            margin-top: 0;
            color: #ff0f68;
            font-size: 28px;
        }

        .subtitle {
            color: #bcbcbc;
            margin-bottom: 30px;
            font-size: 18px;
        }

        label {
            display: block;
            margin-bottom: 12px;
            color: #cfcfcf;
            font-size: 18px;
        }

        input[type="number"] {
            width: 100%;
            padding: 16px 18px;
            font-size: 18px;
            border-radius: 16px;
            border: 1px solid #3a3a3f;
            background: #121216;
            color: white;
            outline: none;
        }

        input[type="number"]:focus {
            border-color: #ff0f68;
            box-shadow: 0 0 0 2px rgba(255, 15, 104, 0.18);
        }

        button {
            margin-top: 18px;
            width: 100%;
            padding: 18px;
            font-size: 20px;
            font-weight: bold;
            border: none;
            border-radius: 18px;
            background: #ff0f68;
            color: white;
            cursor: pointer;
            transition: 0.2s ease;
        }

        button:hover {
            filter: brightness(1.08);
            transform: translateY(-1px);
        }

        .ok {
            background: rgba(24, 122, 70, 0.16);
            color: #86efac;
            padding: 16px 18px;
            border-radius: 16px;
            margin-top: 18px;
            border: 1px solid rgba(134, 239, 172, 0.18);
            font-size: 18px;
        }

        .erro {
            background: rgba(160, 34, 34, 0.18);
            color: #ffb4b4;
            padding: 16px 18px;
            border-radius: 16px;
            margin-top: 18px;
            border: 1px solid rgba(255, 180, 180, 0.18);
            font-size: 18px;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 18px;
            margin-bottom: 24px;
        }

        .stat-card {
            background: rgba(18, 18, 20, 0.96);
            border-radius: 20px;
            padding: 22px;
            border: 1px solid rgba(255,255,255,0.06);
        }

        .stat-label {
            color: #b7b7b7;
            font-size: 16px;
            margin-bottom: 10px;
        }

        .stat-value {
            color: #ffffff;
            font-size: 34px;
            font-weight: bold;
        }

        .item {
            padding: 18px 0;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }

        .item:last-child {
            border-bottom: none;
        }

        .nome {
            font-size: 26px;
            font-weight: bold;
            margin-bottom: 8px;
            color: #ffffff;
        }

        .meta {
            color: #d6d6d6;
            font-size: 18px;
            line-height: 1.6;
        }

        .badge {
            display: inline-block;
            padding: 6px 12px;
            border-radius: 999px;
            font-size: 14px;
            font-weight: bold;
            margin-bottom: 10px;
            background: rgba(255, 15, 104, 0.14);
            color: #ff4b8d;
            border: 1px solid rgba(255, 15, 104, 0.2);
        }

        .empty {
            color: #bdbdbd;
            font-size: 17px;
        }

        @media (max-width: 768px) {
            body {
                padding: 20px;
            }

            h1 {
                font-size: 38px;
            }

            .stats {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>The Grand Tech Gala</h1>
        <h2>Gerenciamento Inteligente de Fila de Espera</h2>

        <div class="box">
            <h3>Executar Processo</h3>
            <p class="subtitle">Informe a quantidade de vagas abertas para promover participantes da fila de espera.</p>

            <form method="post">
                <label>Vagas para Liberar:</label>
                <input type="number" name="vagas_liberar" min="1" required>
                <button type="submit">EXECUTAR PROCESSO PL/SQL</button>
            </form>

            {% if resultado %}
                {% if resultado.sucesso %}
                    <div class="ok">{{ resultado.mensagem }}</div>
                {% else %}
                    <div class="erro">{{ resultado.erro }}</div>
                {% endif %}
            {% endif %}
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-label">Total na fila de espera</div>
                <div class="stat-value">{{ fila_espera|length }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total confirmados</div>
                <div class="stat-value">{{ confirmados|length }}</div>
            </div>
        </div>

        <div class="box">
            <h3>Fila de Espera</h3>
            {% if fila_espera %}
                {% for p in fila_espera %}
                    <div class="item">
                        <div class="badge">Aguardando promoção</div>
                        <div class="nome">{{ p.nome }}</div>
                        <div class="meta">
                            Prioridade: {{ p.prioridade }}<br>
                            Data de inscrição: {{ p.data_inscricao }}
                        </div>
                    </div>
                {% endfor %}
            {% else %}
                <p class="empty">Não há participantes na fila de espera.</p>
            {% endif %}
        </div>

        <div class="box">
            <h3>Participantes Confirmados</h3>
            {% if confirmados %}
                {% for p in confirmados %}
                    <div class="item">
                        <div class="badge">Confirmado</div>
                        <div class="nome">{{ p.nome }}</div>
                        <div class="meta">
                            Prioridade: {{ p.prioridade }}<br>
                            Data de inscrição: {{ p.data_inscricao }}
                        </div>
                    </div>
                {% endfor %}
            {% else %}
                <p class="empty">Não há participantes confirmados.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    resultado = None

    if request.method == "POST":
        vagas_liberar = request.form.get("vagas_liberar", type=int)
        resultado = executar_bloco(vagas_liberar)

    participantes, erro_lista = buscar_participantes()

    if erro_lista:
        resultado = {"sucesso": False, "erro": erro_lista}
        participantes = []

    fila_espera = [p for p in participantes if p["waitlist"] == "SIM"]
    confirmados = [p for p in participantes if p["waitlist"] == "NAO"]

    return render_template_string(
        HTML,
        resultado=resultado,
        fila_espera=fila_espera,
        confirmados=confirmados
    )


app = app