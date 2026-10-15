-- Banco e tabela usados pelo scraper, pela API e pelo painel
CREATE DATABASE IF NOT EXISTS obrasblumenau
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE obrasblumenau;

CREATE TABLE IF NOT EXISTS obras (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  codigo            VARCHAR(20)   NOT NULL,
  secretaria        VARCHAR(100)  NULL,
  descricao         TEXT          NULL,
  logradouro        VARCHAR(255)  NULL,
  intervencao       VARCHAR(100)  NULL,
  situacao          VARCHAR(50)   NULL,
  valor_contratado  DECIMAL(15,2) NULL,
  valor_executado   DECIMAL(15,2) NULL,
  saldo_contrato    DECIMAL(15,2) NULL,
  pct_executado     DECIMAL(5,2)  NULL,
  num_licitacao     VARCHAR(50)   NULL,
  num_contrato      VARCHAR(50)   NULL,
  num_ordem_servico VARCHAR(50)   NULL,
  tipo_recurso      VARCHAR(100)  NULL,
  data_contrato     DATE          NULL,
  inicio_obra       DATE          NULL,
  limite_execucao   DATE          NULL,
  termino_contrato  DATE          NULL,
  empresa_executora VARCHAR(255)  NULL,
  cnpj_empresa      VARCHAR(20)   NULL,
  fiscal_obra       VARCHAR(255)  NULL,
  created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  -- A chave única permite que o INSERT ... ON DUPLICATE KEY UPDATE atualize a obra em vez de duplicar
  UNIQUE KEY uq_obras_codigo (codigo)
);
