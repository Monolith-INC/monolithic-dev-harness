---
date: 2026-07-02
type: ticket
work_item_type: User Story
provider: filesystem
provider_id: local-6869
parent_id: 6868
story_points: 3
tags: [ticket, user-story, demo, auto-fix]
---

# Validação de campos do formulário de login

## 🎯 O quê

Validar os campos do formulário de login e exibir mensagens de erro inline para entradas inválidas.

## 💡 Por quê

Usuários precisam de feedback imediato quando informam email ou senha incorretos, sem submeter o formulário.

## 📋 Comportamento esperado

- Ao sair do campo email com formato inválido, exibir mensagem de erro abaixo do campo.
- Ao tentar submeter com senha vazia, exibir mensagem de erro no campo senha.
- Mensagens de erro desaparecem quando o campo é corrigido.

## ✅ Critérios de Aceite

- [ ] Campo email exibe erro para formato inválido
- [ ] Campo senha exibe erro quando vazio
- [ ] Erros são removidos após correção do campo

## 🔧 Notas Técnicas

- Módulo: autenticação / tela de login
- Validar no blur (email) e no submit (senha)

## 📊 Complexidade

3 pts — driver: Escopo=3 (uma área); Incerteza=1; Integrações=1; Dados=1; QA=2; Rollout=1

| Driver | Score |
|--------|-------|
| Escopo | 3 |
| Incerteza | 1 |
| Integrações | 1 |
| Dados | 1 |
| QA | 2 |
| Rollout | 1 |

## 📄 Descrição Original

> Validar os campos do formulário de login e fornecer feedback ao usuário sobre entradas inválidas.
