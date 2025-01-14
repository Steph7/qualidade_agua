from prometheus_client import Gauge, start_http_server
import requests
import time
import random

# Métrica para enviar os dados brutos ao Prometheus
raw_data_gauge = Gauge('sensor_raw_data', 'Dados brutos do sensor', ['sensor_id'])

# Métrica para salvar a média calculada no Prometheus
average_data_gauge = Gauge('sensor_average_data', 'Média dos últimos 10 dados do sensor', ['sensor_id'])

# URL do Prometheus para consultas (ajuste conforme sua configuração)
url_prometheus = "http://localhost:9090/api/v1/query"

# Função para calcular a média via consulta ao Prometheus
def calculate_average(sensor_id):
    query = f"avg_over_time(sensor_raw_data{{sensor_id='{sensor_id}'}}[10m])"  # Média dos últimos 10 minutos
    try:
        response = requests.get(url_prometheus, params={"query": query})
        response.raise_for_status()
        result = response.json()["data"]["result"]
        if result:
            return float(result[0]["value"][1])  # Retorna o valor da média
        return None
    except requests.exceptions.RequestException as e:
        print(f"Erro ao consultar o Prometheus: {e}")
        return None

# Simula o envio de dados brutos e o cálculo da média
def simulate_data_processing():
    sensor_ids = ["sensor_1", "sensor_2"]  # IDs dos sensores
    while True:
        for sensor_id in sensor_ids:
            # Simula o envio de um dado bruto ao Prometheus
            new_value = random.uniform(10, 100)  # Valor aleatório entre 10 e 100
            raw_data_gauge.labels(sensor_id=sensor_id).set(new_value)
            print(f"Sensor {sensor_id}: Dado bruto enviado = {new_value:.2f}")

            # Calcula a média dos últimos 10 valores via consulta ao Prometheus
            avg_value = calculate_average(sensor_id)
            if avg_value is not None:
                # Armazena a média na nova métrica
                average_data_gauge.labels(sensor_id=sensor_id).set(avg_value)
                print(f"Sensor {sensor_id}: Média calculada = {avg_value:.2f}")

        # Aguarda antes de enviar novos valores
        time.sleep(10)

# Inicializa o servidor HTTP para expor as métricas
if __name__ == "__main__":
    # Inicia o servidor Prometheus na porta 8000
    start_http_server(8000)
    print("Servidor Prometheus rodando na porta 8000...")

    # Inicia o processamento dos dados
    simulate_data_processing()
