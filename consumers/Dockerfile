FROM python:3.10-slim

WORKDIR /app

COPY . /app/consumers

WORKDIR /app/consumers

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "uniswap_swap_consumer.py"]
