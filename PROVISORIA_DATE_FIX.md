# Fix: Extração de Data Inicial em Processos de Naturalização Provisória

## Problema Identificado

A data inicial do processo estava sendo extraída na **etapa errada**, causando falha na extração:

### Fluxo ANTERIOR (incorreto):
1. ❌ Navegar para URL do processo
2. ❌ **Tentar extrair data imediatamente** (página ainda não carregada)
3. ❌ Aguardar tabela carregar
4. ❌ Buscar atividade "Efetuar Distribuição"
5. ❌ Entrar no iframe e extrair dados pessoais

**Resultado**: Data inicial não era extraída porque a página ainda não tinha carregado completamente.

## Solução Implementada

### Fluxo NOVO (correto):
1. ✅ Navegar para URL do processo: `https://justica.servicos.gov.br/workspace/flow/{numero}`
2. ✅ **Aguardar página carregar** (aguardar tabela de atividades)
3. ✅ **AGORA extrair data inicial** do subtitle (após página carregada)
4. ✅ Buscar atividade "Efetuar Distribuição"
5. ✅ Entrar no iframe e extrair dados pessoais

**Resultado**: Data inicial é extraída corretamente **ANTES** de entrar no iframe.

## Alterações Realizadas

### 1. `automation/actions/provisoria_action.py`

#### Método `aplicar_filtros()` (linhas 180-218):
- ✅ Movida extração de data inicial para **DEPOIS** da tabela carregar
- ✅ Adicionado timeout de 3 segundos após navegação
- ✅ Adicionado log detalhado para debug
- ✅ Melhor tratamento de erros na extração

#### Método `_try_extract_data_inicial_from_subtitle()` (linhas 132-139):
- ✅ Aumentado timeout de 6s para 15s
- ✅ XPath mais flexível: `//span[@class='subtitle' or contains(@class,'subtitle')]`
- ✅ Adicionado log do conteúdo do subtitle encontrado

### 2. `Provisória/navegacao_provisoria.py`

#### Método `aplicar_filtros()` (linhas 225-246):
- ✅ Reordenada execução: aguardar tabela **ANTES** de extrair data
- ✅ Adicionado log quando data não é extraída
- ✅ Numeração dos passos atualizada para refletir ordem correta

### 3. `scripts/test_provisoria_idade.py`

#### Melhorias no script de teste:
- ✅ Output mais claro com separadores visuais
- ✅ Verificação explícita da data após `aplicar_filtros()`
- ✅ Logs detalhados de cada passo do processo
- ✅ Resumo final com status ✅/❌

## Ordem de Validação Conforme Especificado

O sistema agora segue a ordem correta de validação:

1. **Calcular idade** (>18 anos → indeferimento automático)
2. **Validar residência PF** (antes/depois dos 10 anos)
3. **Validar documentos via OCR**

## Como Testar

### Teste Básico:
```bash
cd C:\Users\kevin\OneDrive\Desktop\ProjetoRefatorado\ProjetoRefatorado
python scripts\test_provisoria_idade.py 743961
```

### Teste com Múltiplos Processos:
```bash
python scripts\test_provisoria_idade.py 743961 668121 [outros_códigos...]
```

### O que Observar nos Logs:

#### ✅ **SUCESSO** - Data extraída corretamente:
```
[NAV] (Provisória) Aguardando página carregar...
[OK] (Provisória) Tabela de atividades carregada
[DATA] (Provisória) Extraindo data inicial do processo...
[DEBUG] (Provisória) Subtitle encontrado: 'Em andamento - aberto por Cidadão 10 de Jan de 2025 às 14:55...'
[OK] (Provisória) Data inicial extraída: 10/01/2025
[OK] (Provisória) Data inicial propagada para _orig: 10/01/2025

[VERIFICAÇÃO] Data inicial após aplicar_filtros: 10/01/2025
[OK] Data inicial EXTRAÍDA com sucesso no momento correto (antes do iframe)!
```

#### ❌ **FALHA** - Data não extraída:
```
[NAV] (Provisória) Aguardando página carregar...
[OK] (Provisória) Tabela de atividades carregada
[DATA] (Provisória) Extraindo data inicial do processo...
[AVISO] (Provisória) Data inicial não encontrada no subtitle

[VERIFICAÇÃO] Data inicial após aplicar_filtros: None
[ERRO] Data inicial NÃO foi extraída - verificação falhou!
```

## Validação do Cálculo de Idade

Após a data ser extraída, o sistema deve:

1. ✅ Extrair data de nascimento do formulário (dentro do iframe)
2. ✅ Calcular idade usando data inicial e data de nascimento
3. ✅ Aplicar regra de elegibilidade (≤ 17 anos para Provisória)
4. ✅ Determinar decisão final

### Exemplo de Output Esperado:
```
================================================================================
=== RESULTADO DA ANÁLISE ===
================================================================================

[RESULTADO] Data Inicial Processo: 10/01/2025
[RESULTADO] Data Nascimento: 15/03/2010
[RESULTADO] Idade Calculada: 14
[RESULTADO] Elegibilidade: Deferimento
[RESULTADO] Motivo: Idade: 14 anos - Elegível (≤ 17 anos)
================================================================================

[OK] ✅ Idade calculada com sucesso: 14 anos
```

## Tratamento de Erros

O sistema agora inclui fallback robusto:

1. Se o subtitle não for encontrado → log de aviso mas não interrompe
2. Se a extração falhar → propaga None e sistema continua
3. Se a idade não puder ser calculada → análise manual requerida

## Arquivos Modificados

- ✅ `automation/actions/provisoria_action.py` (ordem de extração corrigida)
- ✅ `Provisória/navegacao_provisoria.py` (ordem de extração corrigida)
- ✅ `scripts/test_provisoria_idade.py` (logs melhorados)

## Próximos Passos

1. Execute o teste com processos reais
2. Verifique se a data inicial está sendo extraída corretamente
3. Confirme que a idade está sendo calculada
4. Valide que a decisão final está correta conforme regras

## Notas Técnicas

### Formato de Data Esperado:
- **Entrada (subtitle)**: "10 de Jan de 2025 às 14:55"
- **Saída (normalizada)**: "10/01/2025"

### Elementos HTML:
- **Subtitle**: `<span class="subtitle">Em andamento - aberto por Cidadão 10 de Jan de 2025 às 14:55</span>`
- **Tabela**: `.ant-table-tbody` (aguarda carregar antes de extração)

### Timeout Configurado:
- Aguardar tabela: 12 segundos (refactored) / 10 segundos (legacy)
- Extração subtitle: 15 segundos (refactored) / 40 segundos (legacy via self.wait)

---

**Data da Correção**: 2025-01-XX  
**Autor**: AI Assistant  
**Status**: ✅ Implementado e pronto para teste
