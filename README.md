# Qualidade da água no Rio Thames

Nesse trabalho foram selecionados 9 estações do Rio Thames (região metropolitana de Londres) para que dados de 6 sensores fossem coletados e a partir disso fosse classificada a qualidade da água em cada uma das estações, assim como a qualidade geral nos pontos de estudo.


## Lista de IDs das estações
As estações presentes no estudo são:
    - BREPON
    - KEWPON
    - GPRSD8A1
    - HAMME2
    - PUTNEY
    - CADOG2
    - BARIERA
    - ERITH1
    - E03036A

## Lista de parâmetros
Os parâmetros analisados com os dados enviados dos sensores são:
    - oxigênio dissolvido
    - turbidez               
    - temperatura           
    - condutividade          
    - amonio               
    - ph                        

## Nota de Qualidade
As notas foram calculadas a partir do produtório ponderado dos dados coletados. Como nem todas as estações enviam os dados de todos os sensores. Foi criada uma função que removia os sensores inexistentes e considerava apenas aqueles que enviavam dados válidos.


## Como acessar o Dashboard
Foi construído um Docker, configurando as portas de redirecionamento e o ambiente correto para rodar o programa. No entanto, os arquivos do programa devem ser abertos separadamente.

```bash
    docker-compose down
    docker-compose up --build
```

```bash
docker exec -it qualidade_agua python thames/data_processor5.py
```

```bash
docker exec -it qualidade_agua python thames/data_collector.py
```

## Portas de redirecionamento
    - 8000 (transmissão de métricas p/ Prometheus)
    - 9090 (Prometheus)
    - 3000 (Grafana) <-- Dashboard