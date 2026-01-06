package com.coverage.adapter;

import com.coverage.adapter.agent.CoverageAdapterAgent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.lang.instrument.Instrumentation;
import java.util.Properties;

/**
 * Java Agent entry point for Coverage Adapter
 * Allows Coverage Adapter to be started with the target application using -javaagent
 */
public class PreMain {
    private static final Logger logger = LoggerFactory.getLogger(PreMain.class);
    private static volatile CoverageAdapterAgent agent;

    /**
     * Agent premain method - called by JVM when agent is loaded
     * 
     * @param agentArgs Agent arguments in format: key1=value1,key2=value2,...
     * @param inst Instrumentation instance
     */
    public static void premain(String agentArgs, Instrumentation inst) {
        logger.info("Coverage Adapter Agent starting...");
        
        try {
            // Parse agent arguments
            Properties props = parseAgentArgs(agentArgs);
            
            // Get configuration from agent args or environment variables
            String rabbitmqUrl = getProperty(props, "rabbitmq-url", 
                    System.getenv("COVERAGE_ADAPTER_RABBITMQ_URL"), 
                    "amqp://coverage:coverage123@localhost:5672/");
            
            int flushInterval = Integer.parseInt(getProperty(props, "flush-interval",
                    System.getenv("COVERAGE_ADAPTER_FLUSH_INTERVAL"), "60"));
            
            String jacocoAddress = getProperty(props, "jacoco-address",
                    System.getenv("COVERAGE_ADAPTER_JACOCO_ADDRESS"), "localhost");
            
            int jacocoPort = Integer.parseInt(getProperty(props, "jacoco-port",
                    System.getenv("COVERAGE_ADAPTER_JACOCO_PORT"), "6300"));
            
            String jacocoCliJar = getProperty(props, "jacoco-cli-jar",
                    System.getenv("COVERAGE_ADAPTER_JACOCO_CLI_JAR"),
                    "./jacoco/lib/jacococli.jar");
            
            String jacocoExecFile = getProperty(props, "jacoco-exec-file",
                    System.getenv("COVERAGE_ADAPTER_JACOCO_EXEC_FILE"),
                    "./jacoco.exec");
            
            String jacocoClassfiles = getProperty(props, "jacoco-classfiles",
                    System.getenv("COVERAGE_ADAPTER_JACOCO_CLASSFILES"), null);
            
            if (jacocoClassfiles == null || jacocoClassfiles.isEmpty()) {
                logger.warn("jacoco-classfiles not specified. Coverage Adapter will try to auto-detect from classpath.");
                // Try to auto-detect from classpath
                jacocoClassfiles = System.getProperty("java.class.path");
                if (jacocoClassfiles == null || jacocoClassfiles.isEmpty()) {
                    logger.error("Cannot auto-detect classfiles. Please specify jacoco-classfiles in agent args or COVERAGE_ADAPTER_JACOCO_CLASSFILES environment variable.");
                    return;
                }
            }
            
            String fingerprintFile = getProperty(props, "fingerprint-file",
                    System.getenv("COVERAGE_ADAPTER_FINGERPRINT_FILE"),
                    "~/.coverage_adapter_fingerprint");
            
            // Create and start agent
            agent = new CoverageAdapterAgent(
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
            
            // Register shutdown hook
            Runtime.getRuntime().addShutdownHook(new Thread(() -> {
                logger.info("Coverage Adapter Agent shutting down...");
                if (agent != null) {
                    agent.stop();
                }
            }));
            
            logger.info("Coverage Adapter Agent started successfully");
            
        } catch (Exception e) {
            logger.error("Failed to start Coverage Adapter Agent", e);
        }
    }

    /**
     * Parse agent arguments string into Properties
     * Format: key1=value1,key2=value2,...
     */
    private static Properties parseAgentArgs(String agentArgs) {
        Properties props = new Properties();
        if (agentArgs == null || agentArgs.trim().isEmpty()) {
            return props;
        }
        
        String[] pairs = agentArgs.split(",");
        for (String pair : pairs) {
            String[] kv = pair.split("=", 2);
            if (kv.length == 2) {
                props.setProperty(kv[0].trim(), kv[1].trim());
            }
        }
        
        return props;
    }

    /**
     * Get property value with fallback chain: agent args -> env var -> default
     */
    private static String getProperty(Properties props, String key, String envValue, String defaultValue) {
        String value = props.getProperty(key);
        if (value != null && !value.isEmpty()) {
            return value;
        }
        if (envValue != null && !envValue.isEmpty()) {
            return envValue;
        }
        return defaultValue;
    }
}

