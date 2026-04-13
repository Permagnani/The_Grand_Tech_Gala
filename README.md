# Checkpoint 2 - Integração PL/SQL + Python no Oracle

## Objetivo
Aplicação desenvolvida em Python para integrar uma interface simples com o Oracle Database, executando um bloco anônimo PL/SQL para processar a promoção de participantes da fila de espera, conforme as regras do Desafio 1.

## Tecnologias
- Python
- Streamlit
- Oracle Database
- oracledb
- PL/SQL

## Funcionalidades
- Executar o processo de promoção da fila de espera
- Informar a quantidade de vagas a serem liberadas
- Conectar ao Oracle Database
- Executar bloco anônimo PL/SQL com cursor explícito
- Atualizar participantes promovidos de acordo com prioridade e data de inscrição
- Registrar histórico de alteração na tabela `HISTORICO_STATUS`
- Exibir mensagens de sucesso ou erro na interface
- Listar participantes confirmados e participantes na fila de espera
- Exibir a quantidade total de participantes em espera

## Regras de Negócio Implementadas
- Uso de **cursor explícito** em bloco anônimo
- `JOIN` entre `INSCRICOES` e `USUARIOS`
- Ordenação por **PRIORIDADE** decrescente e **DATA_INSCRICAO** crescente
- Bloqueio de registros com `FOR UPDATE OF`
- Atualização do status dos participantes promovidos
- Registro automático em `HISTORICO_STATUS`

## Estrutura do Projeto
- `cria.sql`: script de criação das tabelas, sequence e dados iniciais
- `app.py`: aplicação em Python responsável pela interface e integração com Oracle

## Responsabilidades da Dupla

### Enzo
Responsável pela camada de banco de dados e lógica PL/SQL.  
Desenvolveu o script de criação da base (`cria.sql`), incluindo tabelas, sequence e dados iniciais para teste. Também implementou o bloco anônimo com **cursor explícito**, realizando a promoção dos participantes da fila de espera com base em prioridade e data de inscrição, além do registro das alterações na tabela `HISTORICO_STATUS`.

### Gustavo
Responsável pela integração em **Python** com o Oracle.  
Desenvolveu a aplicação em Python com Streamlit, realizou a conexão com o Oracle usando `oracledb`, integrou a execução do bloco PL/SQL à interface e exibiu os resultados do processo na tela. Também organizou a visualização dos participantes confirmados e da fila de espera, além do tratamento de mensagens e erros durante a execução.

## Instalação
```bash
pip install -r requirements.txt# The.Grand.Tech.Gala
