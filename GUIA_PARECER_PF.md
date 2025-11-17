# Guia: Parecer da Polícia Federal (PF) na Provisória

## O que é o Parecer PF?

O **Parecer da Polícia Federal** é um campo no formulário onde a PF registra sua análise sobre o processo de naturalização. Para a **Naturalização Provisória**, o parecer é especialmente importante porque:

1. **Determina a idade de ingresso no Brasil** - Se a pessoa entrou antes ou depois dos 10 anos
2. **É a fonte prioritária** - Tem precedência sobre dados do formulário
3. **Pode causar indeferimento automático** - Se indicar ingresso depois dos 10 anos

## Como o Sistema Analisa o Parecer

### Estratégias de Análise (em ordem)

#### 1️⃣ Parecer PF (Prioritário)

O sistema procura por padrões textuais no parecer:

**Padrões "ANTES dos 10 anos"** (aprovado):
- "antes de completar 10"
- "antes dos 10 anos"
- "com menos de 10 anos"
- "menor de 10 anos"
- "idade inferior a 10"
- "ingressou com X anos" (onde X < 10)

**Padrões "DEPOIS dos 10 anos"** (reprovado):
- "após os 10 anos"
- "depois dos 10 anos"
- "após completar 10"
- "maior de 10 anos"
- "idade superior a 10"

#### 2️⃣ Data do Formulário (Fallback)

Se o parecer PF não for conclusivo:
- Extrai data de "ingresso/residência no Brasil" do formulário
- Calcula idade na data de ingresso
- Aprova se idade < 10 anos

#### 3️⃣ Idade Atual (Fallback Final)

Se nenhuma das anteriores funcionar:
- Usa a idade atual do naturalizando
- Aprova se idade atual < 10 anos

## Como Verificar nos Logs

### ✅ Sucesso - Parecer PF Aprovado

```
[PARECER PF] Extraído: Deferimento, Antes 10 anos: True
[OK] (ProvisóriaAction) PF: Ingresso ANTES dos 10 anos identificado
[GATILHO] Aprovado via parecer PF (antes dos 10)
```

### ❌ Falha - Parecer PF Reprovado

```
[PARECER PF] Extraído: Indeferimento, Antes 10 anos: False
[AVISO] (ProvisóriaAction) PF: Ingresso DEPOIS dos 10 anos identificado
[GATILHO] Reprovado via parecer PF (depois dos 10)
```

### ⚠️ Parecer Não Encontrado/Não Conclusivo

```
[AVISO] (ProvisóriaAction) Parecer PF não encontrado
[GATILHO] Parecer PF não conclusivo, usando dados do formulário
[GATILHO] Aprovado via formulário (idade entrada: 7 anos)
```

ou

```
[GATILHO] Aprovado via fallback (idade atual: 8 anos)
```

## Como Verificar nos Resultados

### No arquivo Excel de resultados

Procure pelas colunas:

| Campo | Descrição |
|-------|-----------|
| `justificativa_gatilho_10anos` | Qual estratégia foi usada (PF, formulário, ou fallback) |
| `idade_naturalizando` | Idade atual na data do processo |
| `idade_entrada_brasil` | Idade calculada na data de ingresso (se disponível) |
| `parecer_pf` | Objeto JSON com dados completos do parecer |

### Exemplo de resultado (JSON)

```json
{
  "status": "Processado com sucesso",
  "elegibilidade_final": "deferimento",
  "percentual_final": 100.0,
  "idade_naturalizando": 7,
  "idade_entrada_brasil": 5,
  "justificativa_gatilho_10anos": "PF: ingresso antes dos 10 anos",
  "parecer_pf": {
    "parecer_texto": "O requerente ingressou no Brasil antes de completar 10 anos...",
    "proposta_pf": "Deferimento",
    "antes_10_anos": true,
    "alertas": ["PF indica ingresso antes dos 10 anos"]
  }
}
```

## IDs do Campo Parecer PF

O sistema tenta localizar o parecer PF nos seguintes IDs (em ordem):

1. `CHPF_PARECER` (padrão Ordinária)
2. `PF_PARECER`
3. `PARECER_PF`
4. `PARECER`

Se nenhum for encontrado, o sistema continua usando as estratégias de fallback.

## Troubleshooting

### Problema: "Parecer PF não encontrado"

**Possíveis causas:**
1. Campo do parecer tem ID diferente dos conhecidos
2. Parecer está em outro contexto (fora do iframe)
3. Processo ainda não tem parecer registrado

**Soluções:**
1. Inspecionar HTML manualmente (F12) e procurar por textarea/input com palavra "parecer"
2. Adicionar novo ID em `ids_possiveis` no código (linha ~496 de `provisoria_action.py`)
3. Verificar se o processo realmente tem parecer PF registrado

**Exemplo de como adicionar novo ID:**
```python
ids_possiveis = [
    'CHPF_PARECER', 
    'PF_PARECER', 
    'PARECER_PF', 
    'PARECER',
    'SEU_NOVO_ID_AQUI'  # ← Adicionar aqui
]
```

### Problema: "Parecer extraído mas não identifica idade"

**Sintoma:**
```
[PARECER PF] Extraído: Deferimento, Antes 10 anos: None
[GATILHO] Parecer PF não conclusivo, usando dados do formulário
```

**Causas:**
- Texto do parecer não segue os padrões conhecidos
- Redação diferente do esperado

**Soluções:**
1. Verificar o texto completo do parecer nos logs
2. Adicionar novos padrões regex em `padroes_antes_10` ou `padroes_depois_10`
3. Relatar o novo formato de texto para atualizar os padrões

**Exemplo de como adicionar novo padrão:**
```python
padroes_antes_10 = [
    r'antes\s+de\s+completar\s*10',
    r'antes\s+dos\s*10\s+anos',
    # ... padrões existentes
    r'seu_novo_padrao_aqui',  # ← Adicionar aqui
]
```

### Problema: Parecer contraditório

**Sintoma:**
```
[PARECER PF] Extraído: Indeferimento, Antes 10 anos: True
```

**Causa:**
- PF pode propor indeferimento por outros motivos mesmo que a idade esteja correta
- Sistema só analisa a idade, não outros critérios

**Solução:**
- Verificar campo `alertas` no `parecer_pf` para outros problemas
- Sistema considera apenas `antes_10_anos` para o gatilho de idade

## Campos de Saída Relacionados

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `parecer_pf.parecer_texto` | string | Texto completo do parecer |
| `parecer_pf.proposta_pf` | string | "Deferimento" ou "Indeferimento" |
| `parecer_pf.antes_10_anos` | bool/null | True=antes, False=depois, null=não identificado |
| `parecer_pf.alertas` | array | Lista de observações extraídas |
| `justificativa_gatilho_10anos` | string | Qual estratégia foi usada para aprovar/reprovar |
| `idade_naturalizando` | int | Idade atual do naturalizando |
| `idade_entrada_brasil` | int/null | Idade calculada na data de ingresso |

## Exemplo Prático

### Processo com Parecer PF Claro

**Parecer PF:**
> "O requerente ELISEI KULCHITSKIY, nascido em 08/02/2018, ingressou no território nacional antes de completar 10 anos de idade. Proposta: DEFERIMENTO."

**Análise do sistema:**
1. ✅ Identifica padrão "antes de completar 10"
2. ✅ Define `antes_10_anos = True`
3. ✅ Aprova gatilho via parecer PF
4. ✅ Prossegue para validação dos 4 documentos

**Logs:**
```
[PARECER PF] Extraído: Deferimento, Antes 10 anos: True
[OK] (ProvisóriaAction) PF: Ingresso ANTES dos 10 anos identificado
[GATILHO] Aprovado via parecer PF (antes dos 10)
```

### Processo sem Parecer PF

**Situação:** Campo parecer vazio ou não encontrado

**Análise do sistema:**
1. ⚠️ Não encontra parecer
2. 🔄 Tenta extrair data de ingresso do formulário
3. ✅ Calcula idade: 5 anos na data de ingresso
4. ✅ Aprova gatilho via formulário

**Logs:**
```
[AVISO] (ProvisóriaAction) Parecer PF não encontrado
[GATILHO] Parecer PF não conclusivo, usando dados do formulário
[GATILHO] Aprovado via formulário (idade entrada: 5 anos)
```

## Resumo

✅ **Parecer PF é a fonte prioritária** para determinar idade de ingresso  
✅ **Sistema tem fallbacks automáticos** se parecer não estiver disponível  
✅ **Logs detalhados** mostram exatamente qual estratégia foi usada  
✅ **Fácil adicionar novos padrões** se formato do parecer mudar  
✅ **Resultado sempre inclui `justificativa_gatilho_10anos`** para rastreabilidade
