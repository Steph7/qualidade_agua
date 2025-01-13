import paho.mqtt.client as mqtt
from pymongo import MongoClient, ASCENDING
from prometheus_client import start_http_server, Gauge
from datetime import datetime
import json
import time
import threading
import requests


# Criando uma métrica Gauge 
QUALIDADE_AGUA = Gauge('qualidade_agua', 'Sensores avaliados no Rio Thames', ['estacao', 'sensor', 'data_hora'])

# Definindo as métricas Prometheus
nota_quali_metric = Gauge('nota_qualidade_agua', 'Nota de qualidade da água por estação', ['estacao'])
qualidade_metric = Gauge('qualidade_agua', 'Avaliação da qualidade da água por estação', ['estacao'])

start_http_server(8000) 

# Enviar dados para o Prometheus
def enviar_dados_prometheus(estacao, sensor, data_hora, valor):
    
    QUALIDADE_AGUA.labels(estacao=estacao, sensor=sensor, data_hora=data_hora).set(valor)
    print(f"Enviado - Estação: {estacao}, Sensor: {sensor}, Valor: {valor}, Data_Hora: {data_hora}")
    contador += 1

# Variável de controle para iniciar o processamento
dados_recebidos = threading.Event()

contador = 0

class Estacao:
    def __init__(self, id_estacao, dados):
        self.id_estacao = id_estacao  # ID da estação
        self.dados = dados  # Dicionário com os últimos dados de cada sensor

    def __repr__(self):
        return f"Estacao({self.id_estacao}, {self.dados})"

# Lista de IDs das estações
estacoes_id = [
    "BREPON",  #01
    "KEWPON",  #02
    "GPRSD8A", #03
    "HAMME2",  #04
    "PUTNEY",  #05
    "CADOG2",  #06
    "BARIERA", #07
    "ERITH1",  #08
    "E03036A"  #09        
]

# Lista de parâmetros
parametros_nome = [
    "oxigenio_dissolvido",    #A - 01, 07, 13, 19, 25, 31, 37, 43, 49
    "turbidez",               #B - 02, 08, 14, 20, 26, 32, 38, 44, 50
    "temperatura",            #C - 03, 09, 15, 21, 27, 33, 39, 45, 51
    "condutividade",          #D - 04, 10, 16, 22, 28, 34, 40, 46, 52
    "amonio",                 #E - 05, 11, 17, 23, 29, 35, 41, 47, 53
    "ph"                      #F - 06, 12, 18, 24, 30, 36, 42, 48, 54   
]

# Os pesos devem estar entre 0 e 1 e a soma dos pesos deve ser 1
# Os valores foram adpatados da tabela do PNQA https://portalpnqa.ana.gov.br/indicadores-indice-aguas.aspx
pesos = [
    0.27,   #oxigenio_dissolvido
    0.12,   #turbidez
    0.15,   #temperatura
    0.12,   #condutividade
    0.15,   #amonio
    0.19    #ph
]

# Intervalos em que os parâmetros são bons ou aceitáveis
limites = {
    "oxigenio_dissolvido": (5, 9),   # Oxigênio Dissolvido entre 5 e 9 mg/L
    "turbidez": (0, 4),              # Turbidez entre 0 e 4 NTU
    "temperatura": (0, 30),          # Temperatura entre 0 e 30 graus
    "condutividade": (70, 750),      # Condutividade entre 70 e 750 mS
    "amonio": (0, 0.5),              # Amônio entre 0 e 0.5 mg/L
    "ph": (6.5, 9.5)                 # pH entre 6.5 e 9.5
}

 # Retorna o último valor registrado para o sensor
def obter_ultimo_valor(estacao, sensor):
    query = f"{sensor}{{estacao=\"{estacao}\"}}"
    
    response = requests.get(url_prometheus, params={'query': query})
    
    if response.status_code == 200:
        # Extrai os dados JSON da resposta
        dados = response.json()
        
        if dados['status'] == 'success' and dados['data']['result']:
            # O resultado é uma lista com os dados mais recentes do sensor
            valor = float(dados['data']['result'][0]['value'][1])  # Obtendo o valor da métrica
            return valor
        else:
            print(f"Nenhum dado encontrado para {sensor} na estação {estacao}")
            return None
    else:
        print("Erro na requisição ao Prometheus:", response.status_code)
    return None

# Para cada sensor, obtém o último valor registrado
def obter_dados_estacao(estacao, list_obj):
    url_prometheus = 'http://localhost:9090/api/v1/query'

    dados_estacao = {}
    
    sensores = ['amonio', 'temperatura', 'ph', 'oxigenio_dissolvido', 'turbidez', 'condutividade']
    
    for sensor in sensores:
        valor = obter_ultimo_valor(estacao, sensor)
        if valor is not None:
            dados_estacao[sensor] = valor
    
    estacao_obj = Estacao(estacao, dados_estacao)
    list_obj.append(estacao_obj)

# Retornar um valor entre 0 e 100
def normalizar_intervalo(valor, limite_inferior, limite_superior):
    if limite_inferior <= valor <= limite_superior:
        valor_normalizado = 100
    
    elif valor < limite_inferior:
        valor_normalizado = max(0, 100 - (limite_inferior - valor) * 20)
    
    elif valor > limite_superior:
        valor_normalizado = max(0, 100 - (valor - limite_superior) * 20)

    return valor_normalizado 

# Filtra as notas e pesos válidos (nota > zero)
# Calcula o produtório entre as notas válidas
def calcular_produtorio_com_pesos(notas, pesos):
    notas_validas = [nota for nota in notas if nota > 0]
    pesos_validos = [peso for i, peso in enumerate(pesos) if notas[i] > 0]

    if not notas_validas:
        return 1  # Evita divisão por zero

    soma_pesos_validos = sum(pesos_validos)

    pesos_normalizados = [peso / soma_pesos_validos for peso in pesos_validos]

    produtorio = 1
    for nota, peso_normalizado in zip(notas_validas, pesos_normalizados):
        produtorio *= (nota ** peso_normalizado)

    return produtorio

# Avaliar Qualidade da Água para cada Estação
def nota_qualidade_agua(estacao, pesos, limites):
    notas_estacao = []

    #Avaliar o Oxigênio Dissolvido
    o2 = estacao.get('oxigenio_dissolvido', 0)
    nota_o2 = normalizar_intervalo(o2, limites["oxigenio_dissolvido"][0], limites["oxigenio_dissolvido"][1])
    notas_estacao.append(nota_o2)
    #print(nota_o2)

    #Avaliar a Turbidez
    turb = estacao.get('turbidez', 0)
    nota_turb = normalizar_intervalo(turb, limites["turbidez"][0], limites["turbidez"][1])
    notas_estacao.append(nota_turb)
    #print(nota_turb)

    #Avaliar a Temperatura
    temp = estacao.get('temperatura', 0)
    nota_temp = normalizar_intervalo(temp, limites["temperatura"][0], limites["temperatura"][1])
    notas_estacao.append(nota_temp)
    #print(nota_temp)

    #Avaliar a Condutividade
    cond = estacao.get('condutividade', 0)
    nota_cond = normalizar_intervalo(cond, limites["condutividade"][0], limites["condutividade"][1])
    notas_estacao.append(nota_cond)
    #print(nota_cond)

    #Avaliar a Quantidade de Amônio
    amn = estacao.get('amonio', 0)
    nota_amn = normalizar_intervalo(amn, limites["amonio"][0], limites["amonio"][1])
    notas_estacao.append(nota_amn)
    #print(nota_amn)

    #Avaliar o pH
    ph = estacao.get('ph', 0)
    nota_pH = normalizar_intervalo(ph, limites["ph"][0], limites["ph"][1])
    notas_estacao.append(nota_pH)
    #print(nota_pH)

    produtorio = calcular_produtorio_com_pesos(notas_estacao, pesos)

    return produtorio


def qualificar_agua(produto):
    qualidade = "não qualificado"
    if 0 <= produto <= 25:
        qualidade = "Péssima"

    if 26 <= produto <= 50:
        qualidade = "Ruim"
    
    if 51 <= produto <= 70:
        qualidade = "Razoável"

    if 71 <= produto <= 90:
        qualidade = "Boa"
    
    if 91 <= produto <= 100:
        qualidade = "Ótima"
    
    if produto >= 100:
        qualidade = "Excelente"
    
    return qualidade

# Função de processamento de dados
def loop_processar_dados():
    while True:
        dados_recebidos.wait()
        lista_estacoes = []  # Lista para armazenar as instâncias de Estacao

        # Acessar todas as estações no banco de dados
        for estacao in estacoes_id:
            obter_dados_estacao(estacao, lista_estacoes)

        for estacao in lista_estacoes:
            prod_Teste = nota_qualidade_agua(estacao.dados, pesos, limites)

            estacao = estacao.id_estacao
            colecao = db[estacao] #encontra coleção no BD

            nota_quali = "{:.3f}".format(round(prod_Teste, 3))
            quali = qualificar_agua(prod_Teste)
            
            # Expor as métricas para o Prometheus
            nota_quali_metric.labels(estacao=estacao_nome).set(nota_quali)
            qualidade_metric.labels(estacao=estacao_nome).set(quali)

            print(f"Estação: {estacao_nome}")
            print(f"Nota: {nota_quali:.3f} --- Avaliação: {avaliacao}")
            print("\n")
        
        time.sleep(1080) # Aguarda por 18 minutos

        dados_recebidos.clear()


# Função de callback para salvar os dados recebidos
def on_message(client, userdata, msg):
    global contador
    try:
        # Recebe a mensagem do broker
        dados = json.loads(msg.payload)

        # Salva dados no Banco de Dados
        if "sensor" in dados and "valor" in dados:
            if "sensor" in dados and "valor" in dados:        
            enviar_dados_prometheus(dados['estacao'], dados['sensor'], dados['data_hora'], dados['valor'])        

            if contador == 48:
                dados_recebidos.set()
                contador = 0

        else:
            # Imprime a mensagem recebida
            print(json.dumps(dados, indent=4))
    
    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem JSON.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    


def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao broker com código {rc}")
    # Inscreve no tópico onde a mensagem inicial foi publicada
    client.subscribe("/thames")

# Cria a conexão com o broker
broker = "broker.hivemq.com"
client = mqtt.Client()
client.connect(broker, 1883, 60)

# Inscreve em todos os tópicos
client.subscribe("/thames/#")

# Define a função de callback para mensagens recebidas
client.on_connect = on_connect
client.on_message = on_message

# Loop para escutar novas mensagens (não-bloqueante)
client.loop_start()

# Função para processar os dados
# Inicia o processamento em um thread separado
processamento_thread = threading.Thread(target=loop_processar_dados)
processamento_thread.start()

# Aguardar a interrupção do programa
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Programa interrompido pelo usuário.")