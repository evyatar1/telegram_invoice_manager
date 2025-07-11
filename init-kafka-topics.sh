#!/bin/bash
# init-kafka-topics.sh

echo "Waiting for Kafka broker to be ready..."
/opt/bitnami/kafka/bin/kafka-topics.sh --bootstrap-server broker:9092 --list > /dev/null 2>&1
while [ $? -ne 0 ]; do
  echo "Kafka broker not ready yet. Waiting..."
  sleep 5
  /opt/bitnami/kafka/bin/kafka-topics.sh --bootstrap-server broker:9092 --list > /dev/null 2>&1
done
echo "Kafka broker is ready."

echo "Creating Kafka topic: invoices"
/opt/bitnami/kafka/bin/kafka-topics.sh --create --if-not-exists --topic invoices --partitions 1 --replication-factor 1 --bootstrap-server broker:9092

echo "Creating Kafka topic: telegram-otp-messages"
/opt/bitnami/kafka/bin/kafka-topics.sh --create --if-not-exists --topic telegram-otp-messages --partitions 1 --replication-factor 1 --bootstrap-server broker:9092

echo "Creating Kafka topic: invoice-task"
/opt/bitnami/kafka/bin/kafka-topics.sh --create --if-not-exists --topic invoice-task --partitions 1 --replication-factor 1 --bootstrap-server broker:9092

echo "Kafka topics created."
