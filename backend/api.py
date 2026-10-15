"""API REST (Flask) que expõe as obras gravadas no MySQL em JSON."""

import os

from flask import Flask, jsonify
from flask_cors import CORS
from database import obter_conexao


app = Flask(__name__)

CORS(app)


@app.route("/")
def inicio():

    return jsonify({
        "status": "API Obras Blumenau funcionando"
    })



@app.route("/obras", methods=["GET"])
def listar_obras():

    conexao = obter_conexao()

    try:

        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT *
            FROM obras
            ORDER BY id DESC
            """
        )

        obras = cursor.fetchall()

        # O cursor é um DictCursor, então cada obra já é um dicionário
        return jsonify(obras)


    except Exception as erro:

        return jsonify({
            "erro": str(erro)
        }),500


    finally:

        conexao.close()



@app.route("/obras/<codigo>", methods=["GET"])
def buscar_obra(codigo):

    conexao = obter_conexao()

    try:

        cursor = conexao.cursor()

        cursor.execute(
            """
            SELECT *
            FROM obras
            WHERE codigo = %s
            """,
            (codigo,)
        )

        obra = cursor.fetchone()


        if not obra:

            return jsonify({
                "mensagem":"Obra não encontrada"
            }),404


        return jsonify(obra)


    finally:

        conexao.close()



if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
