import threading
import requests
import time
import paho.mqtt.client as mqtt
import json

# Definir Classe para armazenar os dados coletados
class DadoEstacao:
    def __init__(self, estacao, parametro, valor, data_hora):
        self.estacao = estacao
        self.parametro = parametro
        self.valor = valor
        self.data_hora = data_hora

    def __str__(self):
        return f"Estação: {self.estacao}, Parâmetro: {self.parametro}, Valor: {self.valor} mg/L, Data/Hora: {self.data_hora}"

# Lista de Sensores por estação
sensores = [
    ('estacao_01', ['sensor_01', 'sensor_02','sensor_03', 'sensor_04', 'sensor_05', 'sensor_06']),
    ('estacao_02', ['sensor_07','sensor_08', 'sensor_09', 'sensor_10', 'sensor_11', 'sensor_12']),
    ('estacao_03', ['sensor_13','sensor_14', 'sensor_15', 'sensor_16', 'sensor_17', 'sensor_18']),
    ('estacao_04', ['sensor_19','sensor_20', 'sensor_21', 'sensor_22', 'sensor_23', 'sensor_24']),
    ('estacao_05', ['sensor_25','sensor_26', 'sensor_27', 'sensor_28', 'sensor_19', 'sensor_30']),
    ('estacao_06', ['sensor_31','sensor_32', 'sensor_33', 'sensor_34', 'sensor_35', 'sensor_36']),
    ('estacao_07', ['sensor_37','sensor_38', 'sensor_39', 'sensor_40', 'sensor_41', 'sensor_42']),
    ('estacao_08', ['sensor_43','sensor_44', 'sensor_45', 'sensor_46', 'sensor_47', 'sensor_48']),
    ('estacao_09', ['sensor_49','sensor_50', 'sensor_51', 'sensor_52', 'sensor_53', 'sensor_54'])
]

# Lista de IDs das estações
estacoes = [
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
parametros_url = [
    "-do-i-subdaily-mgL",     #A - Oxigênio Dissolvido
    "-turb-i-subdaily-ntu",   #B - Turbidez
    "-temp-i-subdaily-C",     #C - Temperatura
    "-cond-i-subdaily-mS",    #D - Condutividade
    "-amm-i-subdaily-mgL",    #E - Amônio
    "-ph-i-subdaily"          #F - PH     
]

parametros_nome = [
    "oxigenio_dissolvido",    #A - 01, 07, 13, 19, 25, 31, 37, 43, 49
    "turbidez",               #B - 02, 08, 14, 20, 26, 32, 38, 44, 50
    "temperatura",            #C - 03, 09, 15, 21, 27, 33, 39, 45, 51
    "condutividade",          #D - 04, 10, 16, 22, 28, 34, 40, 46, 52
    "amonio",                 #E - 05, 11, 17, 23, 29, 35, 41, 47, 53
    "ph"                      #F - 06, 12, 18, 24, 30, 36, 42, 48, 54   
]

atualizar_nome_param = dict(zip(parametros_url, parametros_nome))



# Coletar dados de cada estação a cada 15 minutos
def coletar_dados_15min(estacao_id, parametro, dados_coletados):
    url = f"https://environment.data.gov.uk/hydrology/id/measures/{estacao_id}{parametro}/readings.json?latest"

    try:
        # Fazendo a requisição para a API
        resposta = requests.get(url)
        
        # Verificando o código de status da resposta
        #print(f"Código de Status HTTP para {estacao_id}{parametro}: {resposta.status_code}")
        

        if resposta.status_code == 429:
            retry_after = int(resposta.headers.get("Retry-After", 30))
            time.sleep(retry_after)
            # Tentar novamente após o tempo de espera
            resposta = requests.get(url)

        if resposta.status_code == 200:
            try:
                dados = resposta.json()  # Convertendo a resposta em JSON
                
                # Verificar se a chave 'items' está presente na resposta
                if 'items' in dados:
                    for item in dados['items']:
                        # Extraindo os dados
                        valor = item.get('value')  # Valor da medição
                        data_hora = item.get('dateTime')  # Data e hora

                        if parametro in atualizar_nome_param:
                            parametro = atualizar_nome_param[parametro]

                        dados_coletados.append(DadoEstacao(estacao=estacao_id, parametro=parametro, valor=valor, data_hora=data_hora))
                else:
                    print("Nenhum item de medição encontrado na resposta.")
            
            except ValueError as e:
                print("Erro ao tentar parsear o JSON. Conteúdo da resposta:")
                print(resposta.text) 
        else:
            print(f"Erro na requisição {estacao_id}{parametro} : {resposta.status_code}")
            print(f"Conteúdo da resposta (HTML): {resposta.text}")
    
    except requests.exceptions.RequestException as e:
        print(f"Erro ao acessar a API: {e}")

periodicidade = "15 minutos"

def criar_mensagem_incricao():
    mensagem_completa = []  
    for i in range(len(estacoes)):
        sensores_por_estacao = []
        for j in range(len(parametros_nome)):
            sns = {
                    "sensor_id": f"{sensores[i][1][j]}",
                    "data_type": f"{parametros_nome[j]}",
                    "data_interval": periodicidade
                }
            sensores_por_estacao.append(sns)
            
        mensagem_padrao = {
            f"{sensores[i][0]}": f"{estacoes[i]}", 
            "sensors" : sensores_por_estacao
        }           
        mensagem_completa.append(mensagem_padrao)
    return mensagem_completa


def loop_coletar_dados(client):
    dados_coletados = []
    threads = []
    while True:
        for estacao in estacoes:
            for parametro in parametros_url:
                t = threading.Thread(target=coletar_dados_15min, args=(estacao, parametro, dados_coletados))
                threads.append(t)
                t.start()
        
        for t in threads:
            t.join();

        for dado in dados_coletados:
            # Estrutura do tópico: 'thames/<estacao>/<parametro>'
            topico = f"/thames/{dado.estacao}/{dado.parametro}"

            # Dados a serem enviados
            dados_enviar = {
                "estacao": dado.estacao,
                "sensor": dado.parametro,
                "data_hora": dado.data_hora,
                "valor": dado.valor
            }

            # Publica a string no tópico
            client.publish(topico, json.dumps(dados_enviar))
            print(f"Mensagem publicada: {topico} - {dados_enviar}")

            #print("\nDados Coletados:")
            #for dado in dados_coletados:
                #print(f"Estação: {dado.estacao}, Parâmetro: {dado.parametro}, Valor: {dado.valor} mg/L, Data/Hora: {dado.data_hora}")

            time.sleep(1) # Espera um pouco para não sobrecarregar o broker

        # Aguarda por novos dados dos sensores
        time.sleep(1080)  # 18 min 

   
TOPIC = "/thames"

# Função de callback para quando o cliente MQTT se conectar
def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao broker com código {rc}")
    mensagem_inicial = criar_mensagem_incricao()
    client.publish(TOPIC, json.dumps(mensagem_inicial))

    time.sleep(3)

# Cria a conexão com o broker
broker = "broker.hivemq.com"
client = mqtt.Client()

# Define o callback de conexão
client.on_connect = on_connect

# Conecta ao broker
client.connect(broker, 1883, 60)

client.loop_start()
    
loop_coletar_dados(client)

# Aguardar a interrupção do programa
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Programa interrompido pelo usuário.")