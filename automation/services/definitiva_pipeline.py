"""
Pipeline modularizado para Naturalização Definitiva.

Cópia adaptada de `Definitiva/analise_processos.py`, para uso pela
camada `automation.services` sem depender da pasta `Definitiva`.
"""

from __future__ import annotations

import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional


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

        # -----------------------------------------------------------------
        # 1.5) EXTRAIR PARECER PF (ALERTAS)
        # -----------------------------------------------------------------
        parecer_pf_dados = _extrair_parecer_pf(lecom_instance)
        print(f"DEBUG: [MODULAR] Parecer PF extraído - Alertas: {len(parecer_pf_dados.get('alertas', []))}")
        if parecer_pf_dados.get('alertas'):
            print(f"DEBUG: [MODULAR] Alertas PF detectados: {parecer_pf_dados.get('alertas')}")

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
                        
                        # Gerar despacho automático para idade fora da faixa
                        validacoes_temp = {
                            "naturalizacao_provisoria": {"status": "NÃO VERIFICADO", "fonte": "N/A", "atendida": True},  # Assume que tem para gerar despacho correto
                            "documento_identidade": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                            "antecedentes_brasil": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                            "comprovante_residencia_18_20": {"status": "INVÁLIDO", "residencia_atendida": False, "idade_atendida": False, "idade_calculada": idade_na_data_inicial, "score_residencia": 0, "score_idade": 0}
                        }
                        despacho_idade = _gerar_despacho_indeferimento_definitiva(
                            codigo_processo,
                            dados_formulario,
                            validacoes_temp,
                            idade_na_data_inicial,
                            parecer_pf_dados
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
                            "validacoes_individuais": {
                                "naturalizacao_provisoria": {"status": "NÃO VERIFICADO", "fonte": "N/A", "atendida": False},
                                "documento_identidade": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                                "antecedentes_brasil": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                                "comprovante_residencia_18_20": {"status": "INVÁLIDO", "residencia_atendida": False, "idade_atendida": False, "idade_calculada": idade_na_data_inicial, "score_residencia": 0, "score_idade": 0}
                            },
                            "decisao_final": "INDEFERIMENTO",
                            "despacho_automatico": despacho_idade,
                            "parecer_pf": parecer_pf_dados,
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
            
            # Verificar se o campo DOC_PORTARIA tem documento anexado
            print("[VERIFICAÇÃO] Verificando se portaria foi anexada no campo DOC_PORTARIA...")
            portaria_anexada = False
            
            try:
                from selenium.webdriver.common.by import By
                
                # Buscar o campo DOC_PORTARIA
                campo_portaria = lecom_instance.driver.find_element(By.ID, "input__DOC_PORTARIA")
                
                # Verificar se existe o ícone cloud_download dentro deste campo
                try:
                    icone_download = campo_portaria.find_element(
                        By.CSS_SELECTOR, "i.material-icons[type='cloud_download']"
                    )
                    if icone_download:
                        portaria_anexada = True
                        print("[VERIFICAÇÃO] ✅ Portaria ANEXADA no campo DOC_PORTARIA")
                except:
                    print("[VERIFICAÇÃO] ❌ Portaria NÃO anexada no campo DOC_PORTARIA")
                    
            except Exception as e:
                print(f"[VERIFICAÇÃO] ⚠️ Erro ao verificar campo DOC_PORTARIA: {e}")
            
            # Se portaria foi anexada, enviar para análise manual
            if portaria_anexada:
                print("[DECISÃO] Portaria anexada → ANÁLISE MANUAL RECOMENDADA")
                return {
                    "status": "Análise manual recomendada",
                    "motivo": (
                        "Processo 736008 INDEFERIDO automaticamente: "
                        "Naturalização provisória não encontrada no banco de dados oficial "
                        "Cláusula: ANÁLISE MANUAL RECOMENDADA caso exista portaria ou outro "
                        "documento de naturalização anexado no processo."
                    ),
                    "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "nome_processo": dados_formulario.get("nome_completo", "Nome não extraído"),
                    "analise_manual": True,
                    "motivo_manual": "Portaria de naturalização provisória anexada no processo",
                    "validacoes_individuais": {
                        "naturalizacao_provisoria": {"status": "ANÁLISE MANUAL", "fonte": "documento_anexado", "atendida": False},
                        "documento_identidade": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                        "antecedentes_brasil": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                        "comprovante_residencia_18_20": {"status": "NÃO VERIFICADO", "residencia_atendida": False, "idade_atendida": False, "idade_calculada": None, "score_residencia": 0, "score_idade": 0}
                    },
                    "decisao_final": "ANÁLISE MANUAL",
                }
            else:
                # Sem portaria anexada → Indeferimento automático
                print("[DECISÃO] Portaria NÃO anexada → INDEFERIMENTO AUTOMÁTICO")
                
                # Gerar despacho automático para ausência de naturalização provisória
                validacoes_temp = {
                    "naturalizacao_provisoria": {"status": "INVÁLIDO", "fonte": "banco_oficial", "atendida": False},
                    "documento_identidade": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                    "antecedentes_brasil": {"status": "NÃO VERIFICADO", "atendida": False, "score": 0},
                    "comprovante_residencia_18_20": {"status": "NÃO VERIFICADO", "residencia_atendida": False, "idade_atendida": False, "idade_calculada": None, "score_residencia": 0, "score_idade": 0}
                }
                despacho_nat_prov = _gerar_despacho_indeferimento_definitiva(
                    codigo_processo,
                    dados_formulario,
                    validacoes_temp,
                    None,
                    parecer_pf_dados
                )
                
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
                    "validacoes_individuais": validacoes_temp,
                    "decisao_final": "INDEFERIMENTO",
                    "despacho_automatico": despacho_nat_prov,
                    "parecer_pf": parecer_pf_dados,
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

            # Extrair validações individuais de documentos
            validacoes_individuais = {}
            condicoes_obrigatorias = resultado_analise.get("condicoes_obrigatorias", {}) or {}
            resultados_condicoes = condicoes_obrigatorias.get("detalhes", {}) or {}
            
            # Naturalização Provisória
            nat_prov = resultados_condicoes.get("naturalizacao_provisoria", {}) or {}
            validacoes_individuais["naturalizacao_provisoria"] = {
                "status": "VÁLIDO"
                if (naturalizacao_confirmada_via_banco or nat_prov.get("atendida", False))
                else "INVÁLIDO",
                "fonte": "banco_oficial" if naturalizacao_confirmada_via_banco else nat_prov.get("fonte", "documento_anexado"),
                "atendida": bool(naturalizacao_confirmada_via_banco or nat_prov.get("atendida", False)),
            }
            
            # Documento Oficial de Identidade
            doc_id = resultados_condicoes.get("documento_identidade", {}) or {}
            validacoes_individuais["documento_identidade"] = {
                "status": "VÁLIDO" if doc_id.get("atendida", False) else "INVÁLIDO",
                "atendida": doc_id.get("atendida", False),
                "score": doc_id.get("score", 0)
            }
            
            # Certidão de Antecedentes Brasil
            antecedentes = resultados_condicoes.get("sem_antecedentes_criminais", {}) or {}
            validacoes_individuais["antecedentes_brasil"] = {
                "status": "VÁLIDO" if antecedentes.get("atendida", False) else "INVÁLIDO",
                "atendida": antecedentes.get("atendida", False),
                "score": antecedentes.get("score", 0)
            }
            
            # Comprovante de Tempo de Residência (18-20 anos)
            residencia = resultados_condicoes.get("comprovante_residencia", {}) or {}
            idade = resultados_condicoes.get("idade_processo", {}) or {}
            validacoes_individuais["comprovante_residencia_18_20"] = {
                "status": "VÁLIDO" if (residencia.get("atendida", False) and idade.get("atendida", False)) else "INVÁLIDO",
                "residencia_atendida": residencia.get("atendida", False),
                "idade_atendida": idade.get("atendida", False),
                "idade_calculada": idade.get("idade_calculada"),
                "score_residencia": residencia.get("score", 0),
                "score_idade": idade.get("score", 0)
            }
            
            # Debug: Mostrar validações individuais criadas
            print(f"DEBUG: [VALIDAÇÕES] Naturalização Provisória: {validacoes_individuais['naturalizacao_provisoria']}")
            print(f"DEBUG: [VALIDAÇÕES] Documento Identidade: {validacoes_individuais['documento_identidade']}")
            print(f"DEBUG: [VALIDAÇÕES] Antecedentes Brasil: {validacoes_individuais['antecedentes_brasil']}")
            print(f"DEBUG: [VALIDAÇÕES] Residência 18-20: {validacoes_individuais['comprovante_residencia_18_20']}")
            
            # Decisão final: só é deferimento se TODAS as condições forem atendidas
            todas_validas = all([
                validacoes_individuais["naturalizacao_provisoria"]["atendida"],
                validacoes_individuais["documento_identidade"]["atendida"],
                validacoes_individuais["antecedentes_brasil"]["atendida"],
                validacoes_individuais["comprovante_residencia_18_20"]["residencia_atendida"],
                validacoes_individuais["comprovante_residencia_18_20"]["idade_atendida"]
            ])
            
            decisao_final = "DEFERIMENTO" if todas_validas else "INDEFERIMENTO"
            print(f"DEBUG: [DECISÃO] Decisão final: {decisao_final}")
            
            # Gerar despacho automático de indeferimento
            despacho_automatico = ""
            if decisao_final == "INDEFERIMENTO":
                despacho_automatico = _gerar_despacho_indeferimento_definitiva(
                    codigo_processo,
                    dados_formulario,
                    validacoes_individuais,
                    idade_na_data_inicial,
                    parecer_pf_dados
                )
                print(f"DEBUG: [DESPACHO] Despacho automático gerado ({len(despacho_automatico)} caracteres)")

            resultado_final: Dict[str, Any] = {
                "status": "Processado com sucesso",
                "data_processamento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_documentos": len(todos_textos_extraidos),
                "documentos_processados": list(todos_textos_extraidos.keys()),
                "todos_textos_extraidos": todos_textos_extraidos,
                "analise_elegibilidade": resultado_analise,
                "naturalizacao_confirmada_via_banco": naturalizacao_confirmada_via_banco,
                "dados_naturalizacao": dados_naturalizacao,
                "validacoes_individuais": validacoes_individuais,
                "decisao_final": decisao_final,
                "parecer_pf": parecer_pf_dados,
                "despacho_automatico": despacho_automatico,
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


def _extrair_parecer_pf(lecom_instance: Any) -> Dict[str, Any]:
    """Extrai parecer PF e detecta alertas críticos (coleta biométrica, etc.)."""
    parecer_dados = {
        'parecer_texto': '',
        'proposta_pf': 'Não encontrado',
        'alertas': [],
        'nao_compareceu_pf': False,
        'ausencia_coleta_biometrica': False,
    }
    
    try:
        parecer_texto = ''
        
        # Tentar extrair parecer PF usando método do lecom_instance
        if hasattr(lecom_instance, 'extrair_parecer_pf'):
            parecer_resultado = lecom_instance.extrair_parecer_pf()
            if isinstance(parecer_resultado, dict):
                parecer_dados.update(parecer_resultado)
                parecer_texto = parecer_resultado.get('parecer_texto', '')
        
        # Se não conseguiu pelo método, tentar extrair diretamente do campo CHPF_PARECER
        if not parecer_texto:
            try:
                from selenium.webdriver.common.by import By
                campo_parecer = lecom_instance.driver.find_element(By.ID, "CHPF_PARECER")
                parecer_texto = campo_parecer.get_attribute('value') or campo_parecer.text or ''
                if parecer_texto:
                    parecer_dados['parecer_texto'] = parecer_texto
                    print(f"[INFO] Parecer PF extraído diretamente do campo ({len(parecer_texto)} caracteres)")
            except Exception as e:
                print(f"[AVISO] Não foi possível extrair parecer PF do campo: {e}")
            
        if not parecer_texto:
            print("[AVISO] Parecer PF não encontrado ou vazio")
            return parecer_dados
            
        parecer_texto_lower = parecer_texto.lower()
        alertas: List[str] = []
        
        # Detectar ausência de coleta biométrica (padrão da ordinária + definitiva)
        padroes_biometria_ausente = [
            r'art\.?\s*7[ºo°]?\s*,?\s*§?\s*2[ºo°]?\s*,?\s*da\s+portaria\s*n?º?\s*623',
            r'artigo\s+7[ºo°]?\s*,?\s*§?\s*2[ºo°]?\s*,?\s*portaria\s*623',
            r'parágrafo\s+2[ºo°]?\s+do\s+artigo\s+7[ºo°]?\s+da\s+portaria\s*n?º?\s*623',
            r'fulcro\s+no\s+art\.?\s*7[ºo°]?\s*,?\s*§?\s*2[ºo°]?',
            r'com\s+base\s+no\s+art\.?\s*7[ºo°]?\s*,?\s*§?\s*2[ºo°]?',
            r'n[ãa]o\s+compareceu.*coleta.*biom[ée]tric',
            r'n[ãa]o\s+compareceu.*dados\s+biom[ée]tricos',
            r'n[ãa]o\s+compareceu.*agendamento.*coleta',
            r'faltou.*agendamento.*coleta.*biometria',
            r'faltou.*ocasi[õo][ẽe]s.*coleta',
            r'aus[êe]ncia.*coleta\s+biom[ée]trica',
            r'aus[êe]ncia.*sem\s+justificativa.*coleta\s+biom[ée]trica',
            r'deixamos\s+realizar.*coleta.*biometr',
            r'n[ãa]o\s+fora\s+feita.*coleta\s+biom[ée]trica',
            r'n[ãa]o\s+foi\s+feita.*coleta\s+biom[ée]rica',
            r'indeferimento/arquivamento.*art\.?\s*7',
            r'arquivamento/indeferimento.*art\.?\s*7',
            r'sugest[ãa]o\s+de\s+indeferimento/arquivamento',
            r'opini[ãa]o\s+pelo\s+arquivamento.*art\.?\s*7',
            r'opini[ãa]o\s+pelo\s+indeferimento.*art\.?\s*7',
            r"deixamos\s+realizar\s+a\s+coleta.*biometr|dispensa\s+da\s+coleta.*biom[ée]rica|coleta.*biom[ée]tric[oa]s?.*n[ãa]o\s+(foi|fora)\s+(efetuada|feita)|n[ãa]o\s+(foi|fora)\s+(efetuada|feita).*coleta.*biom[ée]tric[oa]s?",
            r'\*\s*coleta\s+de\s+biometria\s+n[ãa]o\s+realizada',
            r'coleta\s+de\s+biometria\s+n[ãa]o\s+realizada',
            r'biometria\s+n[ãa]o\s+realizada',
            r'coleta.*biom[ée]tric[oa]s?\s+n[ãa]o\s+realizada',
        ]
        
        for padrao in padroes_biometria_ausente:
            if re.search(padrao, parecer_texto, re.IGNORECASE):
                parecer_dados['nao_compareceu_pf'] = True
                parecer_dados['ausencia_coleta_biometrica'] = True
                if '⚠️ AUSÊNCIA DE COLETA BIOMÉTRICA CONSTATADA NO PARECER PF' not in alertas:
                    alertas.append('⚠️ AUSÊNCIA DE COLETA BIOMÉTRICA CONSTATADA NO PARECER PF')
                print("[ALERTA PF] Ausência de coleta biométrica detectada")
                break
        
        # Detectar não comparecimento à PF
        padroes_nao_compareceu = [
            r'não\s+compareceu\s+à\s+unidade\s+para\s+apresentar\s+a\s+documentação',
            r'nao\s+compareceu\s+a\s+unidade\s+para\s+apresentar\s+a\s+documentacao',
            r'não\s+compareceu\s+à\s+unidade.*coletar.*dados\s+biométricos',
            r'nao\s+compareceu\s+a\s+unidade.*coletar.*dados\s+biometricos',
            r'requerente\s+não\s+compareceu\s+à\s+unidade',
            r'requerente\s+nao\s+compareceu\s+a\s+unidade',
            r'não\s+compareceu.*apresentar.*documentação.*coletar.*biométricos',
            r'nao\s+compareceu.*apresentar.*documentacao.*coletar.*biometricos',
        ]
        
        for padrao in padroes_nao_compareceu:
            if re.search(padrao, parecer_texto, re.IGNORECASE):
                parecer_dados['nao_compareceu_pf'] = True
                if '🚨 REQUERENTE NÃO COMPARECEU À PF - INDEFERIMENTO AUTOMÁTICO' not in alertas:
                    alertas.append('🚨 REQUERENTE NÃO COMPARECEU À PF - INDEFERIMENTO AUTOMÁTICO')
                print("[ALERTA PF] Não compareceu à PF detectado")
                break
        
        parecer_dados['alertas'] = alertas
        
    except Exception as e:
        print(f"[ERRO] Erro ao extrair parecer PF: {e}")
    
    return parecer_dados


def _gerar_despacho_indeferimento_definitiva(
    codigo_processo: str,
    dados_formulario: Dict[str, Any],
    validacoes_individuais: Dict[str, Any],
    idade_na_data_inicial: Optional[int],
    parecer_pf_dados: Optional[Dict[str, Any]] = None
) -> str:
    """Gera despacho automático de indeferimento para naturalização definitiva."""
    
    
    # Extrair dados do requerente
    nome_completo = dados_formulario.get("nome_completo") or dados_formulario.get("nome") or "NOME NÃO EXTRAÍDO"
    numero_processo = dados_formulario.get("numero_processo") or codigo_processo
    
    # Verificar motivos de indeferimento por prioridade
    motivos = []
    
    # 0. PRIORIDADE MÁXIMA: Não compareceu à PF (coleta biométrica)
    if parecer_pf_dados and parecer_pf_dados.get('nao_compareceu_pf'):
        # Identificar outros motivos de indeferimento
        motivos_adicionais = []
        
        nat_prov = validacoes_individuais.get("naturalizacao_provisoria", {})
        if not nat_prov.get("atendida", False):
            motivos_adicionais.append("não possui naturalização provisória")
        
        doc_id = validacoes_individuais.get("documento_identidade", {})
        if not doc_id.get("atendida", False):
            motivos_adicionais.append("não apresentou documento oficial de identidade")
        
        antecedentes = validacoes_individuais.get("antecedentes_brasil", {})
        if not antecedentes.get("atendida", False):
            motivos_adicionais.append("não apresentou certidão de antecedentes criminais")
        
        residencia = validacoes_individuais.get("comprovante_residencia_18_20", {})
        if not residencia.get("residencia_atendida", False):
            motivos_adicionais.append("não apresentou comprovante de residência")
        
        # Construir texto
        if motivos_adicionais:
            texto_motivos = ", ".join(motivos_adicionais)
            return f"""Código: {codigo_processo}
Assunto: Indeferimento do pedido
Processo: Naturalizar-se nº {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, considerando que o/a requerente foi notificado/a e não compareceu à Polícia Federal para conferência dos documentos originais e coleta biométrica, e que {texto_motivos}, indefere o pedido tendo em vista o não cumprimento das exigências previstas no art. 70 da Lei nº 13.445/2017, c/c art. 227 do Decreto nº 9.199/2017, e §2º, art. 7º da Portaria nº 623 de 13 de novembro de 2020."""
        else:
            return f"""Código: {codigo_processo}
Assunto: Indeferimento do pedido
Processo: Naturalizar-se nº {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, considerando que o/a requerente foi notificado/a e não compareceu à Polícia Federal para conferência dos documentos originais e coleta biométrica, indefere o pedido tendo em vista o não cumprimento das exigências previstas no art. 70 da Lei nº 13.445/2017, c/c art. 227 do Decreto nº 9.199/2017, e §2º, art. 7º da Portaria nº 623 de 13 de novembro de 2020."""
    
    # Cabeçalho padrão para outros casos
    cabecalho = f"""Código: {codigo_processo}
Assunto: Indeferimento do pedido
Processo: Naturalizar-se nº {numero_processo}
Interessado: {nome_completo}

A COORDENADORA DE PROCESSOS MIGRATÓRIOS, no uso da competência delegada pela Portaria nº 623 de 13 de novembro de 2020, publicada no Diário Oficial da União, de 17 de novembro de 2020, indefere o pedido, tendo em vista que """
    
    # 1. PRIORIDADE MÁXIMA: Naturalização provisória não encontrada
    nat_prov = validacoes_individuais.get("naturalizacao_provisoria", {})
    if not nat_prov.get("atendida", False):
        motivo = "a requerente não possui naturalização provisória a ser convertida em definitiva"
        rodape = ", e, portanto, não atende à exigência contida no parágrafo único do art. 70 da Lei nº 13.445/2017."
        despacho_final = cabecalho + motivo + rodape
        return despacho_final
    
    # 2. PRIORIDADE ALTA: Idade fora da faixa 18-20
    residencia_idade = validacoes_individuais.get("comprovante_residencia_18_20", {})
    idade_atendida = residencia_idade.get("idade_atendida", False)
    
    if not idade_atendida and idade_na_data_inicial is not None:
        if idade_na_data_inicial > 20:
            motivo = "a requerente não se enquadra nesse modelo de naturalização definitiva, pois se trata de uma adulta de mais de 20 (vinte) anos de idade"
        else:  # idade < 18
            motivo = "a requerente não se enquadra nesse modelo de naturalização definitiva, pois se trata de um requerente menor de idade"
        rodape = ", e, portanto, não atende à exigência contida no art. 70 da Lei nº 13.445/2017."
        despacho_final = cabecalho + motivo + rodape
        return despacho_final
    
    # 3. DOCUMENTOS FALTANTES (se passou nas verificações acima)
    doc_id = validacoes_individuais.get("documento_identidade", {})
    antecedentes = validacoes_individuais.get("antecedentes_brasil", {})
    residencia = validacoes_individuais.get("comprovante_residencia_18_20", {})
    
    docs_faltantes = []
    
    if not doc_id.get("atendida", False):
        docs_faltantes.append("documento oficial de identidade")
    
    if not antecedentes.get("atendida", False):
        docs_faltantes.append("certidão de antecedentes criminais emitida pelas Justiças Federal e Estadual dos locais onde residiu após completar a maioridade civil")
    
    if not residencia.get("residencia_atendida", False):
        docs_faltantes.append("comprovante de residência")
    
    # Gerar texto baseado nos documentos faltantes
    if len(docs_faltantes) == 1:
        motivo = f"a requerente não apresentou {docs_faltantes[0]}"
        rodape = ", e, portanto, não atende à exigência contida no art. 70 da Lei nº 13.445/2017."
    elif len(docs_faltantes) > 1:
        # Concatenar múltiplos documentos
        partes = []
        for i, doc in enumerate(docs_faltantes):
            if i == 0:
                partes.append(f"a requerente não apresentou {doc}")
            else:
                partes.append(f"não apresentou {doc}")
        
        motivo = ", portanto, ".join(partes)
        rodape = ", nos termos do art. 56 da Portaria nº 623/2020, e, portanto, não atende à exigência contida no art. 70 da Lei nº 13.445/2017."
    else:
        # Caso genérico (não deveria acontecer se chegou aqui)
        motivo = "não foram atendidos os requisitos necessários"
        rodape = ", e, portanto, não atende à exigência contida no art. 70 da Lei nº 13.445/2017."
    
    despacho_final = cabecalho + motivo + rodape
    return despacho_final


__all__ = ["analisar_processo_definitiva"]
