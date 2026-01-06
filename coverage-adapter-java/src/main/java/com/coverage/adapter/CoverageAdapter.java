package com.coverage.adapter;

import com.coverage.adapter.agent.CoverageAdapterAgent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.util.concurrent.Callable;

@Command(name = "coverage-adapter", mixinStandardHelpOptions = true, version = "1.0.0",
        description = "Java coverage adapter for JaCoCo coverage data collection and reporting")
public class CoverageAdapter implements Callable<Integer> {
    private static final Logger logger = LoggerFactory.getLogger(CoverageAdapter.class);

    @Option(names = {"--rabbitmq-url"}, description = "RabbitMQ connection URL", 
            defaultValue = "${COVERAGE_ADAPTER_RABBITMQ_URL:-amqp://coverage:coverage123@localhost:5672/}")
    private String rabbitmqUrl;

    @Option(names = {"--flush-interval"}, description = "Collection interval in seconds", 
            defaultValue = "${COVERAGE_ADAPTER_FLUSH_INTERVAL:-60}")
    private int flushInterval;

    @Option(names = {"--jacoco-address"}, description = "JaCoCo agent address", 
            defaultValue = "${COVERAGE_ADAPTER_JACOCO_ADDRESS:-localhost}")
    private String jacocoAddress;

    @Option(names = {"--jacoco-port"}, description = "JaCoCo agent port", 
            defaultValue = "${COVERAGE_ADAPTER_JACOCO_PORT:-6300}")
    private int jacocoPort;

    @Option(names = {"--jacoco-cli-jar"}, description = "Path to jacococli.jar", 
            defaultValue = "${COVERAGE_ADAPTER_JACOCO_CLI_JAR:-./jacoco/lib/jacococli.jar}")
    private String jacocoCliJar;

    @Option(names = {"--jacoco-exec-file"}, description = "Path to jacoco.exec file", 
            defaultValue = "${COVERAGE_ADAPTER_JACOCO_EXEC_FILE:-./jacoco.exec}")
    private String jacocoExecFile;

    @Option(names = {"--jacoco-classfiles"}, description = "Path to Java class files directory", 
            defaultValue = "${COVERAGE_ADAPTER_JACOCO_CLASSFILES}")
    private String jacocoClassfiles;

    @Option(names = {"--fingerprint-file"}, description = "Path to fingerprint file", 
            defaultValue = "${COVERAGE_ADAPTER_FINGERPRINT_FILE:-~/.coverage_adapter_fingerprint}")
    private String fingerprintFile;

    public static void main(String[] args) {
        int exitCode = new CommandLine(new CoverageAdapter()).execute(args);
        System.exit(exitCode);
    }

    @Override
    public Integer call() {
        try {
            logger.info("Starting Coverage Adapter...");
            
            // Validate required parameters
            if (jacocoClassfiles == null || jacocoClassfiles.isEmpty()) {
                logger.error("jacoco-classfiles is required. Please set COVERAGE_ADAPTER_JACOCO_CLASSFILES environment variable or provide --jacoco-classfiles option.");
                return 1;
            }

            // Create and start agent
            CoverageAdapterAgent agent = new CoverageAdapterAgent(
                    rabbitmqUrl,
                    flushInterval,
                    jacocoAddress,
                    jacocoPort,
                    jacocoCliJar,
                    jacocoExecFile,
                    jacocoClassfiles,
                    fingerprintFile
            );

            agent.start();

            // Keep the main thread alive
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                logger.info("Shutting down Coverage Adapter...");
                agent.stop();
            }));

            // Wait indefinitely
            Thread.currentThread().join();

            return 0;
        } catch (Exception e) {
            logger.error("Failed to start Coverage Adapter", e);
            return 1;
        }
    }
}

