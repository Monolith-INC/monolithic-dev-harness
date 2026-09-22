# Example User Story (dummy — layout reference only)

Canonical shape after `work-item-enricher.prompt.md`. Content is fictional.

## 🎯 O quê

Validar campos de e-mail e senha no formulário de login com mensagens inline quando o formato for
inválido ou os campos estiverem vazios.

## 💡 Por quê

Usuários submetem formulários inválidos e não recebem feedback, gerando frustração e tickets.

## 📋 Comportamento esperado

#### Campo e-mail
- Exibir erro se vazio ao sair do campo
- Aceitar formato RFC 5321 simplificado

#### Campo senha
- Exibir erro se vazio ao submeter
- Desabilitar botão Enviar enquanto campos obrigatórios estiverem inválidos

## ✅ Critérios de Aceite

- [ ] Exibir mensagem clara quando e-mail estiver vazio
- [ ] Exibir mensagem clara quando e-mail tiver formato inválido
- [ ] Exibir mensagem clara quando senha estiver vazia no submit
- [ ] Exibir loading no botão durante autenticação

## 📊 Complexidade

**2 pontos** — Maior driver: Escopo=2 (2-3 artefatos de UI), Incerteza=1, Integrações=1, Dados=1,
QA=2, Rollout=1 → 2 pontos

## 📄 Descrição Original

História fictícia: validar e-mail e senha no login com erros inline.
