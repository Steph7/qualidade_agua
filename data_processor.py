import paho.mqtt.client as mqtt
from prometheus_client import start_http_server, Gauge
import json
from datetime import datetime

# Criando uma métrica Gauge 
QUALIDADE_AGUA = Gauge('qualidade_agua', 'Sensores avaliados no Rio Thames', ['estacao', 'sensor', 'data_hora'])
start_http_server(8000) 

# Enviar dados para o Prometheus
def enviar_dados_prometheus(estacao, sensor, data_hora, valor):
    
    QUALIDADE_AGUA.labels(estacao=estacao, sensor=sensor, data_hora=data_hora).set(valor)
    print(f"Enviado - Estação: {estacao}, Sensor: {sensor}, Valor: {valor}, Data_Hora: {data_hora}")

# Função de callback para salvar os dados recebidos
def on_message(client, userdata, msg):
    try:
        # Recebe a mensagem do broker
        dados = json.loads(msg.payload)

        # Salva dados no Banco de Dados
        if "sensor" in dados and "valor" in dados:        
            enviar_dados_prometheus(dados['estacao'], dados['sensor'], dados['data_hora'], dados['valor'])        

        else:
            # Imprime a mensagem recebida
            print(json.dumps(dados, indent=4))
    
    except json.JSONDecodeError:
        print("Erro ao decodificar a mensagem JSON.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

# Função para processar os dados


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

# Loop para escutar novas mensagens
client.loop_forever()
