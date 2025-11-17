"""
Pipeline modularizado para Naturalização Definitiva.

Cópia adaptada de `Definitiva/analise_processos.py`, para uso pela
camada `automation.services` sem depender da pasta `Definitiva`.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional


def analisar_processo_definitiva(
    lecom_instance: Any,
    codigo_processo: str,
    timeout_global_minutos: Optional[int] = None,
) -> Dict[str, Any]:
    """Analisa um processo do tipo definitiva (versão modular).

    Esta função é semanticamente equivalente à função homônima em
    `Definitiva/analise_processos.py`, mas vive em `automation.services`
    e importa o analisador de elegibilidade modularizado.
    """

    print(f"DEBUG: [MODULAR] Iniciando análise definitiva para processo {codigo_processo}")

    if timeout_global_minutos is None:
        print("DEBUG: [MODULAR] Timeout global DESABILITADO")
        start_time_global = None
    else:
        print(f"DEBUG: [MODULAR] Timeout global configurado: {timeout_global_minutos} minutos")
        start_time_global = time.time()

    try:
        # Sanidade do lecom_instance
        if not lecom_instance or not hasattr(lecom_instance, "driver"):
            return {
                "status": "Erro",
                "erro": "Instância do Lecom inválida (modular)",
                "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        # Checar driver
        try:
            current_url = lecom_instance.driver.current_url  # type: ignore[attr-defined]
            print(f"DEBUG: [MODULAR] Driver ativo - URL atual: {current_url}")
        except Exception as e:
            print(f"DEBUG: [MODULAR] Driver inativo - Erro: {e}")
            return {
                "status": "Erro",
                "erro": f"Driver do navegador inativo: {e}",
                "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        # -----------------------------------------------------------------
        # 1) FORMULÁRIO + IDADE NA DATA INICIAL
        # -----------------------------------------------------------------
        dados_formulario: Dict[str, Any] = {}
        idade_na_data_inicial: Optional[int] = None
        try:
            if hasattr(lecom_instance, "extrair_dados_pessoais_formulario"):
                dados_formulario = lecom_instance.extrair_dados_pessoais_formulario() or {}
                print(
                    "DEBUG: [MODULAR] Dados do formulário extraídos (chaves):",
                    list(dados_formulario.keys()),
                )
        except Exception as e:
            print(f"DEBUG: [MODULAR] Erro ao extrair dados do formulário: {e}")

        # Gate de idade na data inicial do processo (18–20)
        try:
            data_nasc_str = dados_formulario.get("data_nascimento")
            data_inicial_raw = getattr(lecom_instance, "data_inicial_processo", None)

            if data_nasc_str and data_inicial_raw:
                try:
                    from automation.utils.date_utils import normalizar_data_para_ddmmaaaa

                    data_inicial_normalizada = normalizar_data_para_ddmmaaaa(str(data_inicial_raw))
                except Exception as e_norm:
                    print(
                        f"DEBUG: [MODULAR] Erro ao normalizar data inicial do processo: {e_norm}"
                    )
                    data_inicial_normalizada = str(data_inicial_raw)

                from datetime import datetime as _dt

                data_nasc = None
                try:
                    if "/" in data_nasc_str:
                        data_nasc = _dt.strptime(data_nasc_str.strip(), "%d/%m/%Y")
                    elif "-" in data_nasc_str:
                        data_nasc = _dt.strptime(data_nasc_str.strip(), "%d-%m-%Y")
                except Exception as e_nasc:
                    print(
                        f"DEBUG: [MODULAR] Erro ao converter data de nascimento '{data_nasc_str}': {e_nasc}"
                    )
                    data_nasc = None

                data_inicio = None
                try:
                    if "/" in data_inicial_normalizada:
                        data_inicio = _dt.strptime(
                            data_inicial_normalizada.strip(), "%d/%m/%Y"
                        )
                except Exception as e_ini:
                    print(
                        f"DEBUG: [MODULAR] Erro ao converter data inicial '{data_inicial_normalizada}': {e_ini}"
                    )
                    data_inicio = None

                if data_nasc and data_inicio:
                    idade_na_data_inicial = data_inicio.year - data_nasc.year
                    if (data_inicio.month, data_inicio.day) < (data_nasc.month, data_nasc.day):
                        idade_na_data_inicial -= 1

                    print(
                        "DEBUG: [MODULAR] Idade na data inicial do processo",
                        f"({data_inicio.strftime('%d/%m/%Y')}): {idade_na_data_inicial} anos",
                    )

                    dados_formulario["idade_na_data_inicial"] = idade_na_data_inicial
                    dados_formulario["data_inicial_processo"] = data_inicio.strftime(
                        "%d/%m/%Y"
                    )

                    if idade_na_data_inicial < 18 or idade_na_data_inicial > 20:
                        print(
                            "[ERRO] [MODULAR] Idade fora da faixa 18-20 anos na data inicial do processo"
                        )
                        return {
                            "status": "Indeferimento automático",
                            "motivo": (
                                "Idade na data inicial do processo "
                                f"({idade_na_data_inicial} anos) fora da faixa exigida (18-20 anos)"
                            ),
                            "data_processamento": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                            "nome_processo": dados_formulario.get("nome_completo")
                            or dados_formulario.get("nome")
                            or "Nome não extraído",
                            "indeferimento_automatico": True,
                            "motivo_indef": "Idade na data inicial do processo fora da faixa 18-20 anos",
                        }
                else:
                    print(
                        "DEBUG: [MODULAR] Não foi possível calcular idade na data inicial do processo (datas inválidas)"
                    )
            else:
                print(
                    "DEBUG: [MODULAR] Dados insuficientes para cálculo de idade na data inicial do processo"
                )
        except Exception as e:
            print(f"DEBUG: [MODULAR] Erro geral na verificação antecipada de idade: {e}")

        # -----------------------------------------------------------------
        # 2) NATURALIZAÇÃO PROVISÓRIA VIA BANCO (gate 2)
        # -----------------------------------------------------------------
        print(
            "DEBUG: [MODULAR] Verificando naturalização provisória no banco de dados ANTES da análise..."
        )
        naturalizacao_confirmada_via_banco = False
        dados_naturalizacao: Optional[Dict[str, Any]] = None

        if dados_formulario:
            # Implementação própria usando o arquivo SQLite naturalizacao.db
            import sqlite3
            import os

            # Montar campos com fallbacks (nome, mãe, pai)
            nome = (dados_formulario.get("nome_completo") or dados_formulario.get("nome") or "").strip()
            mae_raw = (dados_formulario.get("nome_mae") or dados_formulario.get("mae") or "").strip()
            pai_raw = (dados_formulario.get("nome_pai") or dados_formulario.get("pai") or "").strip()

            def _limpar_filiacao(valor: str) -> str:
                v = (valor or "").strip()
                if not v:
                    return ""
                low = v.lower()
                # Remove textos de rótulo genéricos (não são nomes reais)
                if any(
                    padrao in low
                    for padrao in [
                        "filho de (nome do pai)",
                        "filho de (nome da mãe)",
                        "filha de (nome do pai)",
                        "filha de (nome da mãe)",
                        "nome do pai",
                        "nome da mãe",
                    ]
                ):
                    return ""
                return v

            mae = _limpar_filiacao(mae_raw)
            pai = _limpar_filiacao(pai_raw)

            if not nome:
                print("DEBUG: [MODULAR] Dados insuficientes para consulta ao banco (faltando nome)")
            else:
                db_path = os.path.join(os.getcwd(), "naturalizacao.db")
                if not os.path.exists(db_path):
                    print(f"DEBUG: [MODULAR] Banco naturalizacao.db NÃO encontrado em {db_path}")
                else:
                    try:
                        conn = sqlite3.connect(db_path)
                        conn.row_factory = sqlite3.Row
                        cur = conn.cursor()

                        print(
                            f"DEBUG: [MODULAR] Buscando naturalização em naturalizacao.db para: nome='{nome}', mae='{mae}', pai='{pai}'"
                        )

                        # Heurística: tentar bater exatamente nos campos principais,
                        # usando colunas esperadas pelo legado (nat_nome_*).
                        query = (
                            "SELECT * FROM naturalizacao_provisoria "
                            "WHERE TRIM(UPPER(nat_nome_naturalizado)) = TRIM(UPPER(?)) "
                            "AND TRIM(UPPER(IFNULL(nat_nome_mae, ''))) = TRIM(UPPER(?)) "
                            "AND TRIM(UPPER(IFNULL(nat_nome_pai, ''))) = TRIM(UPPER(?)) "
                            "LIMIT 1"
                        )
                        cur.execute(query, (nome, mae, pai))
                        row = cur.fetchone()

                        if row is None and mae and not pai:
                            # Se não veio nome do pai no formulário, tentar só por nome + mãe
                            print(
                                "DEBUG: [MODULAR] Nenhum registro com pai; tentando nome + mãe apenas"
                            )
                            query2 = (
                                "SELECT * FROM naturalizacao_provisoria "
                                "WHERE TRIM(UPPER(nat_nome_naturalizado)) = TRIM(UPPER(?)) "
                                "AND TRIM(UPPER(IFNULL(nat_nome_mae, ''))) = TRIM(UPPER(?)) "
                                "LIMIT 1"
                            )
                            cur.execute(query2, (nome, mae))
                            row = cur.fetchone()

                        if row is not None:
                            naturalizacao_confirmada_via_banco = True
                            dados_naturalizacao = dict(row)
                            print(
                                "DEBUG: [MODULAR] Naturalização encontrada em naturalizacao.db: ",
                                dados_naturalizacao.get("nat_nome_naturalizado") or dados_naturalizacao.get("nat_nome"),
                            )
                        else:
                            print(
                                "DEBUG: [MODULAR] Nenhum registro correspondente encontrado em naturalizacao.db"
                            )
                    except Exception as e_db:
                        print(f"DEBUG: [MODULAR] Erro ao consultar naturalizacao.db: {e_db}")
                    finally:
                        try:
                            conn.close()
                        except Exception:
                            pass

        lecom_instance.naturalizacao_confirmada_via_banco = naturalizacao_confirmada_via_banco

        if not naturalizacao_confirmada_via_banco:
            print("[ERRO] [MODULAR] Naturalização provisória NÃO encontrada no banco")
            return {
                "status": "Indeferimento automático",
                "motivo": (
                    "Indeferimento automático por ausência de naturalização provisória: "
                    "Naturalização provisória não encontrada no banco de dados oficial"
                ),
                "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "nome_processo": dados_formulario.get("nome_completo", "Nome não extraído"),
                "indeferimento_automatico": True,
                "motivo_indef": "Naturalização provisória não encontrada no banco de dados oficial",
            }

        # -----------------------------------------------------------------
        # 3) DOWNLOAD / OCR DE DOCUMENTOS (sem portaria)
        # -----------------------------------------------------------------
        print("DEBUG: [MODULAR] Iniciando download de documentos (sem portaria)")
        documentos_para_baixar = list(getattr(lecom_instance, "documentos_para_baixar", []))
        if (
            "Portaria de concessão da naturalização provisória"
            in documentos_para_baixar
        ):
            documentos_para_baixar.remove(
                "Portaria de concessão da naturalização provisória"
            )
            print(
                "DEBUG: [MODULAR] LGPD: Portaria de naturalização não será baixada (somente banco)"
            )

        todos_textos_extraidos: Dict[str, str] = {}
        for nome_documento in documentos_para_baixar:
            try:
                print(f"DEBUG: [MODULAR] Tentando baixar {nome_documento}...")
                if nome_documento in getattr(lecom_instance, "textos_ja_extraidos", {}):
                    texto_cache = lecom_instance.textos_ja_extraidos[nome_documento]
                    todos_textos_extraidos[nome_documento] = texto_cache
                    print(
                        f"DEBUG: [MODULAR] {nome_documento}: {len(texto_cache)} caracteres cacheados"
                    )
                    continue

                texto_extraido = lecom_instance.baixar_documento_e_ocr(nome_documento)
                if texto_extraido:
                    try:
                        from data_protection import limpar_texto_ocr

                        texto_protegido = limpar_texto_ocr(texto_extraido)
                        print(
                            f"DEBUG: [MODULAR] Dados sensíveis mascarados em {nome_documento}"
                        )
                    except ImportError:
                        import re as _re

                        texto_protegido = texto_extraido
                        texto_protegido = _re.sub(
                            r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
                            "[CPF MASCARADO]",
                            texto_protegido,
                        )
                        texto_protegido = _re.sub(
                            r"\b\d{2}\.\d{3}\.\d{3}-[0-9X]\b",
                            "[RG MASCARADO]",
                            texto_protegido,
                        )
                    todos_textos_extraidos[nome_documento] = texto_protegido
            except Exception as e_doc:
                print(f"DEBUG: [MODULAR] Erro ao processar {nome_documento}: {e_doc}")

        confirmacao_banco_texto: Optional[str] = None
        if naturalizacao_confirmada_via_banco:
            confirmacao_banco_texto = (
                "CONFIRMAÇÃO VIA BANCO DE DADOS OFICIAL:\n"
                "[OK] Naturalização provisória confirmada via Banco de Dados Oficial!\n"
                "[INFO] Documento de portaria não foi baixado (LGPD)."
            )
        else:
            confirmacao_banco_texto = (
                "VERIFICAÇÃO MANUAL REQUERIDA (LGPD):\n"
                "[AVISO] Naturalização provisória NÃO confirmada via banco oficial."
            )

        documentos_com_confirmacao = dict(todos_textos_extraidos)
        if confirmacao_banco_texto:
            documentos_com_confirmacao[
                "Confirmacao_Naturalizacao_Banco"
            ] = confirmacao_banco_texto

        print(
            f"DEBUG: [MODULAR] Total de documentos processados: {len(todos_textos_extraidos)}"
        )

        # -----------------------------------------------------------------
        # 4) ANÁLISE DE ELEGIBILIDADE (modular)
        # -----------------------------------------------------------------
        print("DEBUG: [MODULAR] Iniciando análise de elegibilidade...")
        try:
            from automation.services.definitiva_elegibilidade_simples import (
                AnalisadorElegibilidadeSimples,
            )

            analisador = AnalisadorElegibilidadeSimples()
            resultado_analise = analisador.analisar_elegibilidade(
                documentos_com_confirmacao,
                dados_formulario,
            )

            resultado_analise["dados_formulario_mascarados"] = {
                "nome_completo": (
                    f"{dados_formulario.get('nome_completo', '')[:2]}***"
                    if dados_formulario.get("nome_completo")
                    else None
                ),
                "data_nascimento": dados_formulario.get("data_nascimento"),
                "idade_calculada": resultado_analise.get("idade_calculada"),
            }
            resultado_analise["lgpd_compliant"] = True
            resultado_analise["naturalizacao_fonte"] = (
                "banco_oficial" if naturalizacao_confirmada_via_banco else "verificacao_manual_requerida"
            )

            resultado_final: Dict[str, Any] = {
                "status": "Processado com sucesso",
                "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_documentos": len(todos_textos_extraidos),
                "documentos_processados": list(todos_textos_extraidos.keys()),
                "todos_textos_extraidos": todos_textos_extraidos,
                "analise_elegibilidade": resultado_analise,
                "naturalizacao_confirmada_via_banco": naturalizacao_confirmada_via_banco,
                "dados_naturalizacao": dados_naturalizacao,
            }

            # Análise de decisões (se disponível)
            if todos_textos_extraidos:
                try:
                    from analise_decisoes import AnalisadorDecisoes  # opcional

                    analisador_dec = AnalisadorDecisoes()
                    analise_decisoes = analisador_dec.analisar_multiplos_documentos(
                        todos_textos_extraidos
                    )
                    resultado_final["analise_decisoes"] = analise_decisoes
                except Exception as e_dec:
                    print(f"DEBUG: [MODULAR] Erro na análise de decisões: {e_dec}")
                    resultado_final["analise_decisoes"] = {
                        "decisao_consolidada": "erro_analise",
                        "erro": str(e_dec),
                    }

            return resultado_final

        except Exception as e:
            print(f"DEBUG: [MODULAR] Erro na análise de elegibilidade: {e}")
            resultado_analise_erro = {
                "elegibilidade": "erro_analise",
                "confianca": 0.0,
                "erro": str(e),
                "lgpd_compliant": True,
                "naturalizacao_fonte": "erro_verificacao",
                "dados_formulario_mascarados": {
                    "nome_completo": (
                        f"{dados_formulario.get('nome_completo', '')[:2]}***"
                        if dados_formulario.get("nome_completo")
                        else None
                    ),
                    "data_nascimento": dados_formulario.get("data_nascimento"),
                },
            }
            resultado_final = {
                "status": "Processado com sucesso",
                "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_documentos": len(todos_textos_extraidos),
                "documentos_processados": list(todos_textos_extraidos.keys()),
                "todos_textos_extraidos": todos_textos_extraidos,
                "analise_elegibilidade": resultado_analise_erro,
                "naturalizacao_confirmada_via_banco": naturalizacao_confirmada_via_banco,
                "dados_naturalizacao": dados_naturalizacao,
            }
            return resultado_final

    except TimeoutError as e:
        print(f"DEBUG: [MODULAR] Timeout global atingido: {e}")
        return {
            "status": "Timeout",
            "erro": f"Timeout global de {timeout_global_minutos} minutos: {e}",
            "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tempo_total_processamento": time.time() - start_time_global
            if start_time_global
            else "N/A",
        }
    except Exception as e:
        print(f"DEBUG: [MODULAR] Erro geral na análise definitiva: {e}")
        return {
            "status": "Erro",
            "erro": f"Erro geral (modular): {e}",
            "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "tempo_total_processamento": time.time() - start_time_global
            if start_time_global
            else "N/A",
        }


__all__ = ["analisar_processo_definitiva"]
