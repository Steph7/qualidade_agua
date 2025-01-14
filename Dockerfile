FROM python:3.9

# Instalação de dependências (se necessário)
RUN apt-get update && apt-get install -y bash

WORKDIR /app

# Copiar os arquivos da aplicação para o container
COPY . .

# Instalar as dependências do Python
RUN pip install -r requirements.txt

# Deixar o container ativo sem executar nenhum processo automaticamente
CMD ["tail", "-f", "/dev/null"]