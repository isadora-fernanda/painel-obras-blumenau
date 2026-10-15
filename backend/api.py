"""API REST (Flask) que devolve as obras gravadas no MySQL em JSON.

Rotas:
    GET /                      status
    GET /obras                 todas as obras (filtros opcionais ?situacao= e ?secretaria=)
    GET /obras/<codigo>        uma obra, ou 404
"""

import os
from datetime import date, datetime
from decimal import Decimal

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from database import obter_conexao

app = Flask(__name__)
app.json.ensure_ascii = False  # mantém os acentos legíveis no JSON
CORS(app)


def _para_json(obra):
    """Datas em AAAA-MM-DD e valores DECIMAL como número."""
    convertida = {}
    for campo, valor in obra.items():
        if isinstance(valor, (date, datetime)):
            valor = valor.isoformat()
        elif isinstance(valor, Decimal):
            valor = float(valor)
        convertida[campo] = valor
    return convertida


def _consultar(sql, parametros=()):
    conexao = obter_conexao()
    try:
        with conexao.cursor() as cursor:
            cursor.execute(sql, parametros)
            return cursor.fetchall()
    finally:
        conexao.close()


@app.get("/")
def inicio():
    return jsonify({"status": "API das obras de Blumenau funcionando"})


@app.get("/obras")
def listar_obras():
    condicoes, parametros = [], []
    for campo in ("situacao", "secretaria"):
        if request.args.get(campo):
            condicoes.append(f"{campo} = %s")
            parametros.append(request.args[campo].upper())

    sql = "SELECT * FROM obras"
    if condicoes:
        sql += " WHERE " + " AND ".join(condicoes)
    obras = _consultar(sql + " ORDER BY codigo", parametros)
    return jsonify([_para_json(obra) for obra in obras])


@app.get("/obras/<codigo>")
def buscar_obra(codigo):
    obras = _consultar("SELECT * FROM obras WHERE codigo = %s", (codigo.upper(),))
    if not obras:
        return jsonify({"erro": f"Obra {codigo} não encontrada"}), 404
    return jsonify(_para_json(obras[0]))


@app.errorhandler(Exception)
def erro(erro):
    if isinstance(erro, HTTPException):  # 404 de rota inexistente, 405...
        return jsonify({"erro": erro.description}), erro.code
    return jsonify({"erro": str(erro)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
