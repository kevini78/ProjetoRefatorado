"""
Service (Analista) - Regras de negócio/decisão do fluxo Aprovar Parecer do Analista
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AnalistaService:
    def calcular_idade(self, data_nascimento, data_referencia=None):
        try:
            if not data_referencia:
                data_referencia = datetime.now()
            elif isinstance(data_referencia, str):
                data_referencia = datetime.strptime(data_referencia, "%d/%m/%Y")
            if isinstance(data_nascimento, str):
                data_nasc = datetime.strptime(data_nascimento, "%d/%m/%Y")
            else:
                data_nasc = data_nascimento
            idade = data_referencia.year - data_nasc.year
            if (data_referencia.month, data_referencia.day) < (data_nasc.month, data_nasc.day):
                idade -= 1
            return idade
        except Exception as e:
            logger.error(f"Erro ao calcular idade: {str(e)}")
            return None

    def analisar_requisitos(self, dados: dict, data_inicio=None) -> dict:
        try:
            resultado = {
                'pode_aprovar_automaticamente': False,
                'motivo_analise_manual': [],
                'status': 'ANÁLISE MANUAL'
            }
            parecer_pf = (dados.get('parecer_pf', '') or '').strip()
            parecer_mj = (dados.get('parecer_mj', '') or '').strip()
            if not parecer_pf or not parecer_mj:
                resultado['motivo_analise_manual'].append("Parecer PF ou MJ não encontrado")
                return resultado
            biometria = (dados.get('biometria', '') or '').strip()
            tipo_naturalizacao = (dados.get('tipo_naturalizacao', '') or '').strip()

            # Exceções (prioridade)
            if (
                parecer_pf == "Propor Indeferimento" and
                parecer_mj == "Propor Indeferimento" and
                biometria not in ["Sim", "Não se aplica"]
            ):
                resultado['pode_aprovar_automaticamente'] = True
                resultado['status'] = 'ENVIAR PARA CPMIG'
                return resultado
            if (
                tipo_naturalizacao == "Provisória" and
                parecer_pf == parecer_mj and
                biometria not in ["Sim", "Não se aplica"]
            ):
                resultado['pode_aprovar_automaticamente'] = True
                resultado['status'] = 'ENVIAR PARA CPMIG'
                return resultado
            if parecer_pf == "Propor Arquivamento" and parecer_mj == "Propor Indeferimento":
                resultado['pode_aprovar_automaticamente'] = True
                resultado['status'] = 'ENVIAR PARA CPMIG'
                return resultado

            if parecer_pf != parecer_mj:
                resultado['motivo_analise_manual'].append("Pareceres PF e MJ divergentes")
                return resultado

            pareceres_validos = ["Propor Deferimento", "Propor Indeferimento", "Propor Arquivamento"]
            if not any(v in parecer_pf for v in pareceres_validos):
                resultado['motivo_analise_manual'].append("Parecer PF não é uma proposta válida")
                return resultado

            if biometria not in ["Sim", "Não se aplica"]:
                resultado['motivo_analise_manual'].append("Biometria não coletada ou inválida")
                return resultado

            # Validar idade se DEFERIMENTO
            if parecer_pf == "Propor Deferimento" and parecer_mj == "Propor Deferimento":
                data_nascimento = (dados.get('data_nascimento', '') or '').strip()
                if not data_nascimento or data_nascimento == "Não encontrado":
                    resultado['motivo_analise_manual'].append("Data de nascimento não encontrada")
                    return resultado
                idade = self.calcular_idade(data_nascimento, data_inicio)
                if idade is None:
                    resultado['motivo_analise_manual'].append("Erro ao calcular idade")
                    return resultado
                if tipo_naturalizacao == "Ordinária" and idade < 18:
                    resultado['motivo_analise_manual'].append(f"Idade insuficiente para Ordinária: {idade} anos")
                    return resultado
                elif tipo_naturalizacao == "Extraordinária" and idade < 18:
                    resultado['motivo_analise_manual'].append(f"Idade insuficiente para Extraordinária: {idade} anos")
                    return resultado
                elif tipo_naturalizacao == "Provisória" and idade > 17:
                    resultado['motivo_analise_manual'].append(f"Idade excessiva para Provisória: {idade} anos")
                    return resultado
                elif tipo_naturalizacao == "Definitiva" and (idade < 18 or idade > 20):
                    resultado['motivo_analise_manual'].append(f"Idade inválida para Definitiva: {idade} anos")
                    return resultado

            resultado['pode_aprovar_automaticamente'] = True
            resultado['status'] = 'ENVIAR PARA CPMIG'
            resultado['motivo_analise_manual'] = []
            return resultado
        except Exception as e:
            logger.error(f"Erro ao analisar requisitos: {str(e)}")
            return {
                'pode_aprovar_automaticamente': False,
                'motivo_analise_manual': [f"Erro na análise: {str(e)}"],
                'status': 'ANÁLISE MANUAL'
            }
