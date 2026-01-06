package com.coverage.adapter.mq;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.rabbitmq.client.Channel;
import com.rabbitmq.client.Connection;
import com.rabbitmq.client.ConnectionFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.util.Map;

public class RabbitMQPublisher {
    private static final Logger logger = LoggerFactory.getLogger(RabbitMQPublisher.class);

    private final String rabbitmqUrl;
    private final ObjectMapper objectMapper;
    private Connection connection;
    private Channel channel;

    public RabbitMQPublisher(String rabbitmqUrl) {
        this.rabbitmqUrl = rabbitmqUrl;
        this.objectMapper = new ObjectMapper();
        connect();
    }

    private void connect() {
        try {
            URI uri = new URI(rabbitmqUrl);
            ConnectionFactory factory = new ConnectionFactory();
            factory.setHost(uri.getHost());
            factory.setPort(uri.getPort() > 0 ? uri.getPort() : 5672);
            
            String userInfo = uri.getUserInfo();
            if (userInfo != null && !userInfo.isEmpty()) {
                String[] credentials = userInfo.split(":", 2);
                factory.setUsername(credentials[0]);
                if (credentials.length > 1) {
                    factory.setPassword(credentials[1]);
                }
            } else {
                factory.setUsername("coverage");
                factory.setPassword("coverage123");
            }

            String path = uri.getPath();
            if (path != null && path.length() > 1) {
                factory.setVirtualHost(path.substring(1));
            } else {
                factory.setVirtualHost("/");
            }

            connection = factory.newConnection();
            channel = connection.createChannel();

            // Declare exchange
            channel.exchangeDeclare("coverage_exchange", "topic", true);

            logger.info("Connected to RabbitMQ: {}", rabbitmqUrl);

        } catch (Exception e) {
            logger.error("Failed to connect to RabbitMQ: {}", rabbitmqUrl, e);
            throw new RuntimeException("Failed to connect to RabbitMQ", e);
        }
    }

    public void publish(Map<String, Object> report) {
        try {
            // Ensure connection is alive
            if (connection == null || !connection.isOpen()) {
                connect();
            }
            if (channel == null || !channel.isOpen()) {
                channel = connection.createChannel();
                channel.exchangeDeclare("coverage_exchange", "topic", true);
            }

            // Serialize to JSON
            String json = objectMapper.writeValueAsString(report);
            byte[] body = json.getBytes("UTF-8");

            // Publish message
            channel.basicPublish(
                    "coverage_exchange",
                    "coverage.report",
                    new com.rabbitmq.client.AMQP.BasicProperties.Builder()
                            .contentType("application/json")
                            .deliveryMode(2) // Persistent
                            .build(),
                    body
            );

            logger.debug("Published coverage report to RabbitMQ");

        } catch (Exception e) {
            logger.error("Failed to publish to RabbitMQ", e);
            // Try to reconnect
            try {
                close();
                connect();
            } catch (Exception ex) {
                logger.error("Failed to reconnect to RabbitMQ", ex);
            }
        }
    }

    public void close() {
        try {
            if (channel != null && channel.isOpen()) {
                channel.close();
            }
            if (connection != null && connection.isOpen()) {
                connection.close();
            }
        } catch (Exception e) {
            logger.warn("Error closing RabbitMQ connection", e);
        }
    }
}

