## BUGS QUE ENCONTREI NO CÓDIGO ORIGINAL (DISCIPLINAS 1 E 2) ANTES DAS MINHAS MUDANÇAS PARA A DISCIPLINA 3 (API)


1. Botão "Reservar" nos cards na tela com a lista de salas (/spaces) estava desabilitado (disabled no HTML), não havia link e não funcionava para nenhum usuário.
2. Tela de nova reserva quebrava com erro 500 se a sala não fosse informada; sendo que não tinha local para selecionar previamente.
3. HTMX (biblioteca dos filtros, admin, etc) não carregava. Pois o hash de segurança do link estava errado no base.html, fazendo o navegador bloquear.
4. Duas pessoas/usuários podiam reservar a mesma sala na mesma data e horário (racing condition).
5. Diretório '/static' não existia, mesmo configurado no código - gerava aviso no console do navegador.
6. Encontrado erros e inconsistência no framework Tailwind CSS (principalmente daisyUI)


Melhorias Pós Entrega:

1. Adicionada logo na tela de login e na barra de navegação.
2. Atualização da versão do Tailwind CSS + DaisyUI.
3. Melhoria do visual para ficar mais institucional. Quanto às cores e telas.