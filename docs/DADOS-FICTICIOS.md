# Dados fictícios

Os dados do desafio são fictícios e não têm ligação com nenhuma empresa real.
Mesmo assim, este repositório não guarda o arquivo original: `data/atendimento/`
traz uma versão derivada, com as mesmas colunas e o mesmo comportamento, em que:

- marcas, transportadora, domínio de e-mail e endereço do proxy de IA são inventados;
- conversas (`CV000001`...) e pedidos (`PED000001`...) têm novos identificadores;
- nome, e-mail, telefone e CPF dos clientes foram substituídos por valores inventados.

Datas, valores, status e regras de política foram mantidos, para os testes
(`python -m pytest`) e os 15 casos (`python -m evals.run_evals`) continuarem valendo.
