# -*- coding: utf-8 -*-
"""
Carregador dinâmico para módulos da pasta Provisória (nomes com acento),
permitindo uso pela nova arquitetura sem alterar a estrutura original.
"""
import os
import importlib.util
from types import ModuleType
from typing import Type, Any
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PROVISORIA_DIR = os.path.join(BASE_DIR, 'Provisória')
ORDINARIA_DIR = os.path.join(BASE_DIR, 'Ordinaria')


def _ensure_sys_path():
    """Garante que diretórios necessários estejam no sys.path.

    - Provisória: para carregar módulos legados (navegacao_provisoria, analise_*)
    - Ordinaria: para que imports como `from ocr_utils import ...` funcionem,
      reaproveitando o módulo Ordinaria/ocr_utils.py.
    """
    if PROVISORIA_DIR not in sys.path:
        sys.path.insert(0, PROVISORIA_DIR)
    if ORDINARIA_DIR not in sys.path:
        sys.path.insert(0, ORDINARIA_DIR)


def _load_module(module_name: str, relative_filename: str) -> ModuleType:
    path = os.path.join(PROVISORIA_DIR, relative_filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Módulo não encontrado: {path}")
    _ensure_sys_path()
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Falha ao criar spec para {path}")
    mod = importlib.util.module_from_spec(spec)
    # Definir __package__ básico para imports locais funcionarem
    try:
        mod.__package__ = 'Provisoria'
    except Exception:
        pass
    spec.loader.exec_module(mod)
    return mod


def load_navegacao_provisoria() -> Type[Any]:
    """Retorna a classe NavegacaoProvisoria carregada dinamicamente."""
    mod = _load_module('navegacao_provisoria', 'navegacao_provisoria.py')
    if not hasattr(mod, 'NavegacaoProvisoria'):
        raise AttributeError('Classe NavegacaoProvisoria não encontrada em navegacao_provisoria.py')
    return getattr(mod, 'NavegacaoProvisoria')


def load_analise_elegibilidade_provisoria() -> Type[Any]:
    """Retorna a classe AnaliseElegibilidadeProvisoria carregada dinamicamente."""
    mod = _load_module('analise_elegibilidade_provisoria', 'analise_elegibilidade_provisoria.py')
    if not hasattr(mod, 'AnaliseElegibilidadeProvisoria'):
        raise AttributeError('Classe AnaliseElegibilidadeProvisoria não encontrada em analise_elegibilidade_provisoria.py')
    return getattr(mod, 'AnaliseElegibilidadeProvisoria')


def load_analise_provisoria_module() -> ModuleType:
    """Carrega o módulo analise_provisoria.py dinamicamente."""
    return _load_module('analise_provisoria', 'analise_provisoria.py')
