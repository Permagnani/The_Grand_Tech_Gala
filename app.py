from flask import Flask, request, render_template_string
import oracledb

app = Flask(__name__)

import os

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
                i.TIPO,
                i.STATUS,
                i.WAITLIST,
                TO_CHAR(i.DATA_INSCRICAO, 'DD/MM/YYYY') AS DATA_INSCRICAO
            FROM INSCRICOES i
            JOIN USUARIOS u ON u.ID_USUARIO = i.ID_USUARIO
            ORDER BY
                CASE WHEN i.WAITLIST = 'SIM' THEN 0 ELSE 1 END,
                i.DATA_INSCRICAO ASC
        """)

        dados = cursor.fetchall()

        participantes = []
        for row in dados:
            participantes.append({
                "id_inscricao": row[0],
                "nome": row[1],
                "plano": row[2],
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
    <title>Python no Oracle</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f6f7fb; color: #222; }
        h1 { margin-bottom: 8px; }
        .box { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
        input, button { padding: 10px; font-size: 16px; }
        button { cursor: pointer; }
        .ok { background: #e7f6ea; color: #1c7c3a; padding: 14px; border-radius: 8px; margin-top: 12px; }
        .erro { background: #fdeaea; color: #b42318; padding: 14px; border-radius: 8px; margin-top: 12px; }
        .item { padding: 10px 0; border-bottom: 1px solid #ddd; }
    </style>
</head>
<body>
    <h1>Python no Oracle</h1>
    <h2>Desafio 1 - Gala Tech</h2>

    <div class="box">
        <form method="post">
            <label>Vagas para Liberar:</label><br><br>
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

    <div class="box">
        <h3>Total na fila de espera: {{ fila_espera|length }}</h3>
        {% for p in fila_espera %}
            <div class="item">
                <strong>{{ p.nome }}</strong><br>
                Plano: {{ p.plano }}<br>
                Data de inscrição: {{ p.data_inscricao }}
            </div>
        {% endfor %}
    </div>

    <div class="box">
        <h3>Total confirmados: {{ confirmados|length }}</h3>
        {% for p in confirmados %}
            <div class="item">
                <strong>{{ p.nome }}</strong><br>
                Plano: {{ p.plano }}<br>
                Data de inscrição: {{ p.data_inscricao }}
            </div>
        {% endfor %}
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