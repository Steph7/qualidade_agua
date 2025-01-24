import paho.mqtt.client as mqtt
from pymongo import MongoClient, ASCENDING
from prometheus_client import start_http_server, Gauge
from prometheus_api_client import PrometheusConnect
from datetime import datetime, timedelta
import json
import time
import threading
import requests

# Conectar ao Prometheus
prometheus_url = 'http://prometheus:9090'
prom = PrometheusConnect(url=prometheus_url, disable_ssl=True)

# Definir alerta inatividade
alerta_inatividade = Gauge('alerta_inatividade', 'Tempo de inatividade de cada sensor em segundos', ['estacao_id',  'sensor'])

# Definir coordenadas Estacoes
latitude_estacao = Gauge('latitude_estacao', 'Latitude das Estações do Rio Thames', ['estacao'])
longitude_estacao = Gauge('longitude_estacao', 'Longitude das Estações do Rio Thames', ['estacao'])

# Criando uma métrica Gauge 
QUALIDADE_AGUA = Gauge('qualidade_agua', 'Sensores avaliados no Rio Thames', ['estacao', 'sensor', 'data_hora'])

# Definindo as métricas Prometheus
nota_qualidade = Gauge('nota_qualidade_agua', 'Nota de qualidade da água por estação', ['estacao'])
avaliacao_qualidade = Gauge('avaliacao_qualidade', 'Avaliação da qualidade da água por estação', ['estacao'])

start_http_server(8000)

# Enviar dados para o Prometheus
def enviar_dados_prometheus(estacao, sensor, data_hora, valor):
    
    QUALIDADE_AGUA.labels(estacao=estacao, sensor=sensor, data_hora=data_hora).set(valor)
    print(f"Enviado - Estação: {estacao}, Sensor: {sensor}, Valor: {valor}, Data_Hora: {data_hora}")

# Variável de controle para iniciar o processamento
dados_recebidos = threading.Event()
lock = threading.Lock()

dados_estacao = {}
lista_estacoes = []  # Lista para armazenar as instâncias de Estacao

class Estacao:
    def __init__(self, id_estacao, dados):
        self.id_estacao = id_estacao  # ID da estação
        self.dados = dados  # Dicionário com os últimos dados de cada sensor

    def __repr__(self):
        return f"Estacao({self.id_estacao}, {self.dados})"

# Coordenadas das Estações
coordenadas_estacoes = [
    ("BREPON", 51.479811, -0.303104),
    ("KEWPON", 51.486026, -0.282838),
    ("HAMME2", 51.489978, -0.234679),
    ("PUTNEY", 51.467276, -0.215313),
    ("CADOG2", 51.482879, -0.166442)
]

# Lista de IDs das estações
estacoes_id = [
    "BREPON",  #01
    "KEWPON",  #02
    "HAMME2",  #03
    "PUTNEY",  #04
    "CADOG2"   #05       
]

# Lista de parâmetros
parametros_nome = [
    "oxigenio_dissolvido",    #A - 01, 07, 13, 19, 25
    "salinidade",             #B - 02, 08, 14, 20, 26
    "temperatura",            #C - 03, 09, 15, 21, 27
    "condutividade",          #D - 04, 10, 16, 22, 28
    "amonio",                 #E - 05, 11, 17, 23, 29
    "ph"                      #F - 06, 12, 18, 24, 30  
]

# Os pesos devem estar entre 0 e 1 e a soma dos pesos deve ser 1
# Os valores foram adpatados da tabela do PNQA https://portalpnqa.ana.gov.br/indicadores-indice-aguas.aspx
pesos = [
    0.27,   #oxigenio_dissolvido
    0.12,   #salinidade
    0.15,   #temperatura
    0.12,   #condutividade
    0.15,   #amonio
    0.19    #ph
]

# Intervalos em que os parâmetros são bons ou aceitáveis
limites = {
    "oxigenio_dissolvido": (5, 9),   # Oxigênio Dissolvido entre 5 e 9 mg/L
    "salinidade": (0, 0.5),          # Salinidade entre 0 e 0.5 psU
    "temperatura": (0, 30),          # Temperatura entre 0 e 30 graus
    "condutividade": (70, 750),      # Condutividade entre 70 e 750 mS
    "amonio": (0, 0.5),              # Amônio entre 0 e 0.5 mg/L
    "ph": (6.5, 9.5)                 # pH entre 6.5 e 9.5
}

for estacao, lat, lon in coordenadas_estacoes:
    latitude_estacao.labels(estacao=estacao).set(lat)
    longitude_estacao.labels(estacao=estacao).set(lon)

# Checar inatividade dos sensores
def checar_inatividade():
    for est_id in estacoes_id:
        for parametro in parametros_nome:
            query = f'qualidade_agua{{estacao="{est_id}", sensor="{parametro}"}}'
        
            resultado_query = prom.custom_query(query=query)

            if resultado_query:
                ultimo_data_hora_str = resultado_query[-1]['metric']['data_hora']
                ultimo_data_hora_dt = datetime.fromisoformat(ultimo_data_hora_str)
                ultimo_data_hora_int = int(ultimo_data_hora_dt.timestamp())

                hora_agora = datetime.utcnow()

                tempo_inatividade = hora_agora - ultimo_data_hora_dt

                # Verificar se a diferença é maior que 10 minutos
                if tempo_inatividade > timedelta(minutes=20):
                    tempo_inatividade_min = tempo_inatividade.total_seconds()/60

                    alerta_inatividade.labels(estacao_id=est_id, sensor=parametro).set(tempo_inatividade_min)

                    print(f"ALERTA! {parametro} da {est_id} inativo a mais de {round(tempo_inatividade_min, 2)} minutos.")

            else:
                print(f"Sem retorno de dados para a query: {query}.")

            time.sleep(10) # Aguarda 10s para evitar sobrecarga



# Para cada sensor, obtém o último valor registrado
def obter_dados_sensor(estacao, sensor, valor, list_obj):
    if valor is not None:
        # Procura a estação na lista de objetos
        estacao_encontrada = False
        with lock:
            for est in list_obj:
                if est.id_estacao == estacao:
                    # Se a estação já existir, adiciona ou atualiza o sensor
                    est.dados[sensor] = valor
                    estacao_encontrada = True
                    break
            
            # Se a estação não for encontrada, cria um novo objeto e adiciona à lista
            if not estacao_encontrada:
                dados_estacao = {sensor: valor}  # Cria o dicionário com o sensor e valor
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

    #Avaliar a Salinidade
    sal = estacao.get('salinidade', 0)
    nota_sal = normalizar_intervalo(sal, limites["salinidade"][0], limites["salinidade"][1])
    notas_estacao.append(nota_sal)
    #print(nota_sal)

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
    notas_estacao.clear()
    return produtorio


def qualificar_agua(produto):
    qualidade = -1
    if 0 <= produto < 26:
        qualidade =  1 # Péssima

    if 26 <= produto < 51:
        qualidade = 2 # Ruim
    
    if 51 <= produto < 71:
        qualidade = 3 # Razoável

    if 71 <= produto < 91:
        qualidade = 4 # Boa
    
    if 91 <= produto < 100:
        qualidade = 5 # Ótima
    
    if produto >= 100:
        qualidade = 6 # Excelente
    
    return qualidade


# Função de processamento de dados
def loop_processar_dados():
    timeout_ocorrido = False
    while True:
        if not dados_recebidos.wait(timeout=40):  # Timeout de 40 segundos
            if not timeout_ocorrido:
                timeout_ocorrido = True

        if timeout_ocorrido:
            #print("Timeout atingido! Processando dados...")

            #print(lista_estacoes)
            if lista_estacoes:
                with lock:
                    for estacao in lista_estacoes:
                        prod_Teste = nota_qualidade_agua(estacao.dados, pesos, limites)

                        estacao = estacao.id_estacao

                        nota_quali = round(prod_Teste, 3)
                        quali = qualificar_agua(prod_Teste)
                        
                        # Expor as métricas para o Prometheus
                        nota_qualidade.labels(estacao=estacao).set(nota_quali)
                        avaliacao_qualidade.labels(estacao=estacao).set(quali)

                        print(f"Enviado - Estação: {estacao}, Nota: {nota_quali}, Avaliação: {quali}")

                    # Limpar dados
                    lista_estacoes.clear()

        dados_recebidos.clear()

        timeout_ocorrido = False

# Função de callback para salvar os dados recebidos
def on_message(client, userdata, msg):
    try:
        # Recebe a mensagem do broker
        dados = json.loads(msg.payload)

        # Salva dados no Banco de Dados
        if "sensor" in dados and "valor" in dados:
            # Valida os campos esperados
            estacao = dados.get("estacao")
            sensor = dados.get("sensor")
            valor = dados.get("valor")
            data_hora = dados.get("data_hora")      

            enviar_dados_prometheus(estacao, sensor, data_hora, valor)
            obter_dados_sensor(estacao, sensor, valor, lista_estacoes)       

            dados_recebidos.set()

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

# Inicia uma thread para monitorar inatividade dos sensores
# Criando e iniciando a thread para monitorar a estação "BREPON"
alerta_thread = threading.Thread(target=checar_inatividade)
alerta_thread.start()

# Aguardar a interrupção do programa
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Programa interrompido pelo usuário.")
    client.loop_stop()  # Interrompe o loop do MQTT
    client.disconnect() 