#Desenvolver um back end com api -
#postman - teste http -> verificar respostas da API
# 1. OBJETIVO
# 2. URLBASE
# 3. ENDPOINTS
# 4. RECURSOS DISPONIBILIZADOS

#VAMOS CRIAR UMA API:
"""
1. CONSULTAR
2. CRIAR
3. EDITAR
4. EXCLUIR
C.R.U.D
"""

from flask import Flask, jsonify, request

app = Flask(__name__)
#APP -> Representa a aplicação FLASK
#__NAME__ Identifica que o modulo da aplicação

cursos = [
    {"id": 1,
        "titulo": "automação",
        "autor": "WEG e SENAI"
    },
    {"id": 2,
        "titulo": "eletromecanica",
        "autor": "senai"
    },
    {"id": 3,
        "titulo": "mecanica",
        "autor": "Sesc"
    },
    {"id": 4,
        "titulo": "eletrotécnica",
        "autor": "SENAI"
    },
    {"id": 5,
        "titulo": "cibersistemas para automação",
        "autor": "WEG e SENAI"
    },
    {"id": 6,
        "titulo": "informática",
        "autor": "Sesc"
    },
    {"id": 7,
        "titulo": "segurança do trabalho",
        "autor": "SENAI"
    },
    {"id": 8,
        "titulo": "logística",
        "autor": "Sesc"
    },
    {"id": 9,
        "titulo": "mecatrônica",
        "autor": "SENAI"
    },
    {"id": 10,
        "titulo": "programação de computadores",
        "autor": "WEG e SENAI"
    },
]
#Consultar livros - Criar uma função
def obter_cursos():
    return jsonify(cursos)

#Criar as Rotas: /LIVROS
@app.route("/cursos", methods = ["GET"])
def obter_cursos():
    return jsonify(cursos)

#Inicialização do servidor local]

app.run(
    host="localhost",
    port=5000,
    debug=True
)
