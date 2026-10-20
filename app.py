"""
API DE CURSOS - CRUD completo com Flask
=======================================

1. OBJETIVO
   Disponibilizar uma API REST para gerenciar um catálogo de cursos
   (consultar, criar, editar e excluir), com validação dos dados,
   filtros, ordenação e paginação.

2. URL BASE
   http://localhost:5000/api/v1

3. ENDPOINTS
   GET     /saude                -> verifica se a API está no ar
   GET     /estatisticas         -> resumo do catálogo
   GET     /cursos               -> lista cursos (filtros, ordenação, paginação)
   GET     /cursos/<id>          -> consulta um curso
   POST    /cursos               -> cria um curso
   PUT     /cursos/<id>          -> substitui um curso (todos os campos)
   PATCH   /cursos/<id>          -> edita parcialmente um curso
   DELETE  /cursos/<id>          -> exclui um curso

4. RECURSOS DISPONIBILIZADOS
   Recurso "curso":
     id             int      gerado pela API
     titulo         str      obrigatório (até 100 caracteres)
     autor          str      obrigatório (até 100 caracteres)
     carga_horaria  int      obrigatório, em horas (> 0)
     nivel          str      básico | intermediário | avançado (padrão: básico)
     modalidade     str      presencial | ead | híbrido (padrão: presencial)
     ativo          bool     padrão: true
     criado_em      str      data/hora ISO 8601 (UTC), gerado pela API
     atualizado_em  str      data/hora ISO 8601 (UTC), gerado pela API

   Parâmetros de GET /cursos (todos opcionais):
     busca, autor, nivel, modalidade, ativo,
     ordenar_por (id|titulo|autor|carga_horaria), ordem (asc|desc),
     pagina, por_pagina

Como executar:
   pip install flask
   python api_cursos.py

Exemplos para testar no Postman:
   GET    http://localhost:5000/api/v1/cursos?autor=senai&ordenar_por=titulo
   POST   http://localhost:5000/api/v1/cursos
          Body (raw/JSON):
          {"titulo": "Redes Industriais", "autor": "WEG e SENAI",
           "carga_horaria": 120, "nivel": "intermediário"}
   PATCH  http://localhost:5000/api/v1/cursos/1      {"ativo": false}
   DELETE http://localhost:5000/api/v1/cursos/1

Observação: os dados ficam em memória. Ao reiniciar o servidor, voltam
ao estado inicial. Para persistir, troque a lista por um banco de dados
(por exemplo, SQLite com SQLAlchemy).
"""

from __future__ import annotations

import logging
import math
import os
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

from flask import Flask, jsonify, request, url_for
from werkzeug.exceptions import HTTPException

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------

# app    -> representa a aplicação Flask
# __name__ -> identifica o módulo da aplicação
app = Flask(__name__)
app.json.ensure_ascii = False  # mantém acentos legíveis no JSON
app.json.sort_keys = False     # mantém a ordem dos campos como definida

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("api_cursos")

API_PREFIXO = "/api/v1"

NIVEIS = ("básico", "intermediário", "avançado")
MODALIDADES = ("presencial", "ead", "híbrido")
CAMPOS_EDITAVEIS = ("titulo", "autor", "carga_horaria", "nivel", "modalidade", "ativo")
CAMPOS_ORDENAVEIS = ("id", "titulo", "autor", "carga_horaria")

POR_PAGINA_PADRAO = 10
POR_PAGINA_MAXIMO = 50


# ---------------------------------------------------------------------------
# BANCO DE DADOS EM MEMÓRIA
# ---------------------------------------------------------------------------

def _agora() -> str:
    """Data/hora atual em UTC no formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _novo_curso(
    id_: int,
    titulo: str,
    autor: str,
    carga_horaria: int,
    nivel: str = "básico",
    modalidade: str = "presencial",
    ativo: bool = True,
) -> dict[str, Any]:
    agora = _agora()
    return {
        "id": id_,
        "titulo": titulo,
        "autor": autor,
        "carga_horaria": carga_horaria,
        "nivel": nivel,
        "modalidade": modalidade,
        "ativo": ativo,
        "criado_em": agora,
        "atualizado_em": agora,
    }


cursos: list[dict[str, Any]] = [
    _novo_curso(1, "Automação", "WEG e SENAI", 200, "intermediário"),
    _novo_curso(2, "Eletromecânica", "SENAI", 240, "intermediário"),
    _novo_curso(3, "Mecânica", "Sesc", 160),
    _novo_curso(4, "Eletrotécnica", "SENAI", 220, "intermediário"),
    _novo_curso(5, "Cibersistemas para Automação", "WEG e SENAI", 300, "avançado", "híbrido"),
    _novo_curso(6, "Informática", "Sesc", 80, "básico", "ead"),
    _novo_curso(7, "Segurança do Trabalho", "SENAI", 120),
    _novo_curso(8, "Logística", "Sesc", 100, "básico", "híbrido"),
    _novo_curso(9, "Mecatrônica", "SENAI", 280, "avançado"),
    _novo_curso(10, "Programação de Computadores", "WEG e SENAI", 180, "intermediário", "ead"),
    _novo_curso(11, "CLP e Redes Industriais", "WEG e SENAI", 120, "avançado"),
    _novo_curso(12, "Internet das Coisas com ESP32", "SENAI", 60, "intermediário", "híbrido"),
    _novo_curso(13, "Desenho Técnico Mecânico", "Sesc", 80),
    _novo_curso(14, "Manutenção Industrial", "SENAI", 160, "intermediário"),
    _novo_curso(15, "Segurança da Informação", "SENAI", 100, "avançado", "ead"),
]

_proximo_id = max(c["id"] for c in cursos) + 1


def _gerar_id() -> int:
    global _proximo_id
    novo = _proximo_id
    _proximo_id += 1
    return novo


# ---------------------------------------------------------------------------
# ERROS E RESPOSTAS PADRONIZADAS
# ---------------------------------------------------------------------------

class ApiError(Exception):
    """Erro de negócio que vira uma resposta JSON padronizada."""

    def __init__(
        self,
        mensagem: str,
        status: HTTPStatus = HTTPStatus.BAD_REQUEST,
        detalhes: Any = None,
    ) -> None:
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = int(status)
        self.detalhes = detalhes


def _resposta_erro(mensagem: str, status: int, detalhes: Any = None):
    corpo: dict[str, Any] = {"erro": {"codigo": status, "mensagem": mensagem}}
    if detalhes:
        corpo["erro"]["detalhes"] = detalhes
    return jsonify(corpo), status


@app.errorhandler(ApiError)
def _tratar_api_error(e: ApiError):
    return _resposta_erro(e.mensagem, e.status, e.detalhes)


@app.errorhandler(HTTPException)
def _tratar_http_exception(e: HTTPException):
    mensagens = {
        404: "Recurso não encontrado.",
        405: "Método não permitido para este recurso.",
        415: "Tipo de conteúdo não suportado. Use application/json.",
    }
    return _resposta_erro(mensagens.get(e.code, e.description), e.code)


@app.errorhandler(Exception)
def _tratar_erro_inesperado(e: Exception):
    log.exception("Erro inesperado: %s", e)
    return _resposta_erro(
        "Erro interno do servidor.", HTTPStatus.INTERNAL_SERVER_ERROR
    )


@app.after_request
def _registrar_requisicao(resposta):
    log.info("%s %s -> %s", request.method, request.full_path.rstrip("?"), resposta.status_code)
    return resposta


# ---------------------------------------------------------------------------
# FUNÇÕES AUXILIARES
# ---------------------------------------------------------------------------

def _buscar_curso(curso_id: int) -> dict[str, Any]:
    for curso in cursos:
        if curso["id"] == curso_id:
            return curso
    raise ApiError(f"Curso {curso_id} não encontrado.", HTTPStatus.NOT_FOUND)


def _ler_json() -> dict[str, Any]:
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        raise ApiError("Envie um corpo JSON válido (objeto).", HTTPStatus.BAD_REQUEST)
    return dados


def _validar_curso(dados: dict[str, Any], parcial: bool = False) -> dict[str, Any]:
    """
    Valida e normaliza os dados de um curso.
    parcial=False -> POST/PUT (campos obrigatórios exigidos, padrões aplicados)
    parcial=True  -> PATCH (apenas os campos enviados são validados)
    """
    erros: dict[str, Any] = {}
    limpo: dict[str, Any] = {}

    desconhecidos = sorted(set(dados) - set(CAMPOS_EDITAVEIS))
    if desconhecidos:
        erros["campos_desconhecidos"] = desconhecidos

    # Textos obrigatórios
    for campo in ("titulo", "autor"):
        if campo in dados:
            valor = dados[campo]
            if not isinstance(valor, str) or not valor.strip():
                erros[campo] = "deve ser um texto não vazio."
            elif len(valor.strip()) > 100:
                erros[campo] = "deve ter no máximo 100 caracteres."
            else:
                limpo[campo] = valor.strip()
        elif not parcial:
            erros[campo] = "campo obrigatório."

    # Carga horária
    if "carga_horaria" in dados:
        valor = dados["carga_horaria"]
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            erros["carga_horaria"] = "deve ser um número inteiro maior que zero."
        else:
            limpo["carga_horaria"] = valor
    elif not parcial:
        erros["carga_horaria"] = "campo obrigatório."

    # Campos com lista fixa de opções
    for campo, opcoes, padrao in (
        ("nivel", NIVEIS, "básico"),
        ("modalidade", MODALIDADES, "presencial"),
    ):
        if campo in dados:
            valor = dados[campo]
            if not isinstance(valor, str) or valor.strip().lower() not in opcoes:
                erros[campo] = f"deve ser um destes valores: {', '.join(opcoes)}."
            else:
                limpo[campo] = valor.strip().lower()
        elif not parcial:
            limpo[campo] = padrao

    # Ativo
    if "ativo" in dados:
        if not isinstance(dados["ativo"], bool):
            erros["ativo"] = "deve ser true ou false."
        else:
            limpo["ativo"] = dados["ativo"]
    elif not parcial:
        limpo["ativo"] = True

    if erros:
        raise ApiError("Dados inválidos.", HTTPStatus.UNPROCESSABLE_ENTITY, erros)

    return limpo


def _parametro_inteiro(nome: str, padrao: int, minimo: int, maximo: int | None = None) -> int:
    bruto = request.args.get(nome)
    if bruto is None:
        return padrao
    try:
        valor = int(bruto)
    except ValueError:
        raise ApiError(f"O parâmetro '{nome}' deve ser um número inteiro.")
    if valor < minimo or (maximo is not None and valor > maximo):
        limite = f"entre {minimo} e {maximo}" if maximo is not None else f"maior ou igual a {minimo}"
        raise ApiError(f"O parâmetro '{nome}' deve estar {limite}.")
    return valor


def _parametro_booleano(nome: str) -> bool | None:
    bruto = request.args.get(nome)
    if bruto is None:
        return None
    texto = bruto.strip().lower()
    if texto in ("true", "1", "sim"):
        return True
    if texto in ("false", "0", "nao", "não"):
        return False
    raise ApiError(f"O parâmetro '{nome}' deve ser true ou false.")


# ---------------------------------------------------------------------------
# ROTAS
# ---------------------------------------------------------------------------

@app.route(f"{API_PREFIXO}/saude", methods=["GET"])
def saude():
    """Verificação simples para saber se a API está respondendo."""
    return jsonify({"status": "ok", "hora_utc": _agora(), "total_cursos": len(cursos)})


@app.route(f"{API_PREFIXO}/estatisticas", methods=["GET"])
def estatisticas():
    """Resumo do catálogo: totais e agrupamentos."""

    def contar_por(campo: str) -> dict[str, int]:
        contagem: dict[str, int] = {}
        for curso in cursos:
            contagem[curso[campo]] = contagem.get(curso[campo], 0) + 1
        return dict(sorted(contagem.items()))

    total_horas = sum(c["carga_horaria"] for c in cursos)
    return jsonify({
        "dados": {
            "total_cursos": len(cursos),
            "cursos_ativos": sum(1 for c in cursos if c["ativo"]),
            "carga_horaria_total": total_horas,
            "carga_horaria_media": round(total_horas / len(cursos), 1) if cursos else 0,
            "por_autor": contar_por("autor"),
            "por_nivel": contar_por("nivel"),
            "por_modalidade": contar_por("modalidade"),
        }
    })


@app.route(f"{API_PREFIXO}/cursos", methods=["GET"])
def listar_cursos():
    """Lista cursos com filtros, ordenação e paginação."""
    resultado = list(cursos)

    # Filtros
    busca = request.args.get("busca", "").strip().casefold()
    if busca:
        resultado = [
            c for c in resultado
            if busca in c["titulo"].casefold() or busca in c["autor"].casefold()
        ]

    autor = request.args.get("autor", "").strip().casefold()
    if autor:
        resultado = [c for c in resultado if autor in c["autor"].casefold()]

    nivel = request.args.get("nivel", "").strip().lower()
    if nivel:
        if nivel not in NIVEIS:
            raise ApiError(f"O parâmetro 'nivel' deve ser um destes: {', '.join(NIVEIS)}.")
        resultado = [c for c in resultado if c["nivel"] == nivel]

    modalidade = request.args.get("modalidade", "").strip().lower()
    if modalidade:
        if modalidade not in MODALIDADES:
            raise ApiError(
                f"O parâmetro 'modalidade' deve ser um destes: {', '.join(MODALIDADES)}."
            )
        resultado = [c for c in resultado if c["modalidade"] == modalidade]

    ativo = _parametro_booleano("ativo")
    if ativo is not None:
        resultado = [c for c in resultado if c["ativo"] is ativo]

    # Ordenação
    ordenar_por = request.args.get("ordenar_por", "id").strip().lower()
    if ordenar_por not in CAMPOS_ORDENAVEIS:
        raise ApiError(
            f"O parâmetro 'ordenar_por' deve ser um destes: {', '.join(CAMPOS_ORDENAVEIS)}."
        )
    ordem = request.args.get("ordem", "asc").strip().lower()
    if ordem not in ("asc", "desc"):
        raise ApiError("O parâmetro 'ordem' deve ser 'asc' ou 'desc'.")

    resultado.sort(
        key=lambda c: c[ordenar_por].casefold() if isinstance(c[ordenar_por], str) else c[ordenar_por],
        reverse=(ordem == "desc"),
    )

    # Paginação
    pagina = _parametro_inteiro("pagina", 1, 1)
    por_pagina = _parametro_inteiro("por_pagina", POR_PAGINA_PADRAO, 1, POR_PAGINA_MAXIMO)
    total_itens = len(resultado)
    total_paginas = max(1, math.ceil(total_itens / por_pagina))
    inicio = (pagina - 1) * por_pagina

    return jsonify({
        "dados": resultado[inicio:inicio + por_pagina],
        "paginacao": {
            "pagina": pagina,
            "por_pagina": por_pagina,
            "total_itens": total_itens,
            "total_paginas": total_paginas,
        },
    })


@app.route(f"{API_PREFIXO}/cursos/<int:curso_id>", methods=["GET"])
def obter_curso(curso_id: int):
    """Consulta um curso pelo id."""
    return jsonify({"dados": _buscar_curso(curso_id)})


@app.route(f"{API_PREFIXO}/cursos", methods=["POST"])
def criar_curso():
    """Cria um novo curso."""
    dados = _validar_curso(_ler_json())

    duplicado = any(
        c["titulo"].casefold() == dados["titulo"].casefold()
        and c["autor"].casefold() == dados["autor"].casefold()
        for c in cursos
    )
    if duplicado:
        raise ApiError(
            "Já existe um curso com este título e autor.", HTTPStatus.CONFLICT
        )

    curso = _novo_curso(_gerar_id(), **dados)
    cursos.append(curso)

    resposta = jsonify({"dados": curso})
    resposta.status_code = HTTPStatus.CREATED
    resposta.headers["Location"] = url_for("obter_curso", curso_id=curso["id"])
    return resposta


@app.route(f"{API_PREFIXO}/cursos/<int:curso_id>", methods=["PUT"])
def substituir_curso(curso_id: int):
    """Substitui todos os campos editáveis de um curso."""
    curso = _buscar_curso(curso_id)
    dados = _validar_curso(_ler_json(), parcial=False)
    curso.update(dados)
    curso["atualizado_em"] = _agora()
    return jsonify({"dados": curso})


@app.route(f"{API_PREFIXO}/cursos/<int:curso_id>", methods=["PATCH"])
def editar_curso(curso_id: int):
    """Edita apenas os campos enviados."""
    curso = _buscar_curso(curso_id)
    corpo = _ler_json()
    if not corpo:
        raise ApiError("Envie ao menos um campo para editar.")
    dados = _validar_curso(corpo, parcial=True)
    curso.update(dados)
    curso["atualizado_em"] = _agora()
    return jsonify({"dados": curso})


@app.route(f"{API_PREFIXO}/cursos/<int:curso_id>", methods=["DELETE"])
def excluir_curso(curso_id: int):
    """Exclui um curso. Responde 204 (sem conteúdo) em caso de sucesso."""
    curso = _buscar_curso(curso_id)
    cursos.remove(curso)
    return "", HTTPStatus.NO_CONTENT


# ---------------------------------------------------------------------------
# INICIALIZAÇÃO DO SERVIDOR LOCAL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host=os.getenv("API_HOST", "localhost"),
        port=int(os.getenv("API_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "1") == "1",
    )