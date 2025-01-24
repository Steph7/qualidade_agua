# Qualidade da água no Rio Thames

Nesse trabalho foram selecionadas 5 estações do Rio Thames (região metropolitana de Londres) para que dados de 6 sensores fossem coletados. A partir disso, foi classificada a qualidade da água em cada uma das estações, assim como a qualidade geral nos pontos de estudo.

A **API** utilizada foi: https://environment.data.gov.uk/hydrology/doc/reference .

No total, o trabalho capta dados em intervalos de 15 minutos de 30 sensores.

## Lista de IDs das estações
As estações presentes no estudo são:

    1. BREPON
    2. KEWPON
    3. HAMME2
    4. PUTNEY
    5. CADOG2


## Lista de parâmetros
Os parâmetros analisados com os dados enviados dos sensores são:

    1. oxigênio dissolvido
    2. salinidade
    3. temperatura
    4. condutividade
    5. amônio
    6. pH                 

## Como os dados foram publicados no broker

O broker utilizado foi o **HIVEmqtt**. As mensagens foram publicados nos tópicos nos seguintes formatos:

### Tópicos
```python
    # Estrutura do tópico: 'thames/<estacao>/<parametro>'
    topico = f"/thames/{dado.estacao}/{dado.parametro}"
```

### Mensagens
```python
    # Dados a serem enviados
    dados_enviar = {
        "estacao": dado.estacao,
        "sensor": dado.parametro,
        "data_hora": dado.data_hora,
        "valor": dado.valor
    }
```
### Publicação e Logs
```python
    # Publica a string no tópico
    client.publish(topico, json.dumps(dados_enviar))
    print(f"Mensagem publicada: {topico} - {dados_enviar}")
```

## Como os dados foram registrados no Banco de Dados

### Métricas

```python
alerta_inatividade = Gauge('alerta_inatividade', 'Tempo de inatividade de cada sensor em segundos', ['estacao_id',  'sensor'])
latitude_estacao = Gauge('latitude_estacao', 'Latitude das Estações do Rio Thames', ['estacao'])
longitude_estacao = Gauge('longitude_estacao', 'Longitude das Estações do Rio Thames', ['estacao'])
QUALIDADE_AGUA = Gauge('qualidade_agua', 'Sensores avaliados no Rio Thames', ['estacao', 'sensor', 'data_hora'])
nota_qualidade = Gauge('nota_qualidade_agua', 'Nota de qualidade da água por estação', ['estacao'])
avaliacao_qualidade = Gauge('avaliacao_qualidade', 'Avaliação da qualidade da água por estação', ['estacao'])
```

### Registro dos dados

```python 
QUALIDADE_AGUA.labels(estacao=estacao, sensor=sensor, data_hora=data_hora).set(valor)
```
As demais métricas foram salvas de forma análoga.

### Alertas

É utilizada uma QUERY para consultar o Banco de Dados do **Prometheus** (porta 9090) e retornar o timestamp do último dado captado pelo sensor.

```python
    query = f'qualidade_agua{{estacao="{est_id}", sensor="{parametro}"}}'
```

A partir disso, calcula-se se o intervalo é maior do que 20 minutos para detectar se o mesmo está enviando os dados corretamente. Como os sensores enviam dados de 15 em 15 minutos, optou-se por esperar por um intervalo superior a 20 minutos para que a inatividade fosse notificada.

```python

    tempo_inatividade = hora_agora - ultimo_data_hora_dt

    # Verificar se a diferença é maior que 20 minutos
    if tempo_inatividade > timedelta(minutes=20):
        tempo_inatividade_min = tempo_inatividade.total_seconds()/60

        alerta_inatividade.labels(estacao_id=est_id, sensor=parametro).set(tempo_inatividade_min)

        print(f"ALERTA! {parametro} da {est_id} inativo a mais de {round(tempo_inatividade_min, 2)} minutos.")
```

## Nota de Qualidade
As notas foram calculadas a partir do produtório ponderado dos dados coletados.

### Limites de cada parâmetro
    1. Oxigênio Dissolvido entre 5 e 9 mg/L
    2. Salinidade entre 0 e 0.5 psU
    3. Temperatura entre 0 e 30 ºC
    4. Condutividade entre 70 e 750 mS
    5. Amônio entre 0 e 0.5 mg/L
    6. pH entre 6.5 e 9.5

### Pesos de cada parâmetro
    1. 0.27,   #oxigenio_dissolvido
    2. 0.12,   #salinidade
    3. 0.15,   #temperatura
    4. 0.12,   #condutividade
    5. 0.15,   #amonio
    6. 0.19    #ph

Somatório dos pesos = 1

### Cálculos Realizados

#### Atribuição de notas

Após a coleta dos valores captados pelos sensores, foi atribuída uma nota normalizada entre 0 e 100 para cada um dos parâmetros analisados.

```python
    if limite_inferior <= valor <= limite_superior:
        valor_normalizado = 100
    
    elif valor < limite_inferior:
        valor_normalizado = max(0, 100 - (limite_inferior - valor) * 20)
    
    elif valor > limite_superior:
        valor_normalizado = max(0, 100 - (valor - limite_superior) * 20)
```

De modo que se estivesse dentro do intervalo de limites, ganhava 100, e se estivesse fora, recebia a penalização na nota como disposto acima.

#### Produtório ponderado de notas

Depois de calculada a nota para cada parâmetro, é feito o produtório ponderado com os pesos definidos.

$$
IQA = \prod_{i=1}^{n} A_i^{p_i}
$$

onde A é a nota daquele parâmetro de 0 a 100 e p é o peso daquele parâmetro.

O resultado final foi uma nota entre 0 e 100, que foi salva no Banco de Dados do **Prometheus**.

#### Classificação das notas

Dos índices IQA (Índices de Qualidade da Água obtidos após o produtório), foi feita a seguinte classificação.

    1.  0 <= IQA < 26: qualidade =  1 # Péssima
    2. 26 <= IQA < 51: qualidade =  2 # Ruim
    3. 51 <= IQA < 71: qualidade =  3 # Razoável
    4. 71 <= IQA < 91: qualidade =  4 # Boa
    5. 91 <= IQA < 100: qualidade = 5 # Ótima
    6. IQA >= 100:      qualidade = 6 # Excelente

Obs.: Como o **Grafana** precisa de receber dados númericos, as notas finais de classificação foram enviadas nesse formato e posteriormente convertidas nas referentes descrições, como relacionado acima.

## Como acessar o Dashboard
Foi construído um Docker, configurando as portas de redirecionamento e o ambiente correto para rodar o programa. No entanto, os arquivos do programa devem ser abertos separadamente.

```bash
    docker-compose up --build
```

O data_processor é o arquivo que processa os dados. Ele coleta os dados publicados no broker, realiza os cálculos e salva no Banco de Dados do **Prometheus**. 

```bash
docker exec -it qualidade_agua python thames/data_processor.py
```

O data_collector é o programa que busca os dados na API e os publica no broker **HIVEmqtt**. 

```bash
docker exec -it qualidade_agua python thames/data_collector.py
```

Para abrir o dashboardo do **Granafa**, foram preservadas as definições padrões:

```bash
usuário: admin
senha: admin
```

## Portas de redirecionamento
    * 8000 (transmissão de métricas p/ Prometheus)
    * 9090 (Prometheus)
    * 3000 (Grafana) <-- Dashboard

## Desconectar

Para encerar corretamente:

```bash
    docker-compose down
```

Os demais terminais podem apenas ser fechados utilizando ctrl + C.