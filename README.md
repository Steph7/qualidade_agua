# Qualidade da água no Rio Thames

Nesse trabalho foram selecionados 9 estações do Rio Thames (região metropolitana de Londres) para que dados de 6 sensores fossem coletados e a partir disso fosse classificada a qualidade da água em cada uma das estações, assim como a qualidade geral nos pontos de estudo.


## Lista de IDs das estações
As estações presentes no estudo são:
    1. BREPON
    2. KEWPON
    3. GPRSD8A1
    4. HAMME2
    5. PUTNEY
    6. CADOG2
    7. BARIERA
    8. ERITH1
    9. E03036A

## Lista de parâmetros
Os parâmetros analisados com os dados enviados dos sensores são:
    1. oxigênio dissolvido
    2. turbidez               
    3. temperatura           
    4. condutividade          
    5. amonio               
    8. ph                        

## Nota de Qualidade
As notas foram calculadas a partir do produtório ponderado dos dados coletados. Como nem todas as estações enviam os dados de todos os sensores. Foi criada uma função que removia os sensores inexistentes e considerava apenas aqueles que enviavam dados válidos.


## Como acessar o Dashboard
Foi construído um Docker, configurando as portas de redirecionamento e o ambiente correto para rodar o programa. No entanto, os arquivos do programa devem ser abertos separadamente.

```bash
    docker-compose down
    docker-compose up --build
```

O data_processor é o arquivo que processa os dados. Ele coleta os dados publicados no broker, realiza os cálculos e salva no Banco de Dados do Prometheus. 

```bash
docker exec -it qualidade_agua python thames/data_processor5.py
```

O data_collector é o programa que busca os dados na API e os publica no broker HIVEmqtt. 

```bash
docker exec -it qualidade_agua python thames/data_collector.py
```

## Portas de redirecionamento
    * 8000 (transmissão de métricas p/ Prometheus)
    * 9090 (Prometheus)
    * 3000 (Grafana) <-- Dashboard