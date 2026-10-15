"""Conexão com o MySQL. As credenciais vêm do arquivo .env (veja .env.example)."""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()


def obter_conexao():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        port=int(os.getenv("DB_PORT", 3306)),
        database=os.getenv("DB_DATABASE", "obrasblumenau"),
        cursorclass=pymysql.cursors.DictCursor
    )
