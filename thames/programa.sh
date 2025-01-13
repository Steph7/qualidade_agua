#!/bin/bash
# Inicia o primeiro processo
python data_processor3.py &

# Inicia o segundo processo
python data_collector.py &

# Aguarda ambos os processos para manter o container ativo
wait