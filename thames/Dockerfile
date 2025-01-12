# Use uma imagem base do Python
FROM python:3.9-slim

# Defina o diretório de trabalho dentro do container
WORKDIR /app

# Copie todos os arquivos da pasta local para o diretório /app no container
COPY . /app

# Instala as dependências do seu projeto
RUN pip install --no-cache-dir -r requirements.txt

# Torna o script executável
RUN chmod +x /app/programa.sh

# Exponha a porta onde seu serviço vai rodar
EXPOSE 8000

# Comando para rodar o script shell
CMD ["./programa.sh"]