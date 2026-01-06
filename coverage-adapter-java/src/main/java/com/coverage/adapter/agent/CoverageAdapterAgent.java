package com.coverage.adapter.agent;

import com.coverage.adapter.git.GitInfo;
import com.coverage.adapter.git.GitInfoCollector;
import com.coverage.adapter.jacoco.JaCoCoClient;
import com.coverage.adapter.mq.RabbitMQPublisher;
import com.coverage.adapter.model.CoverageData;
import com.coverage.adapter.model.CoverageRange;
import com.coverage.adapter.util.FingerprintCalculator;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.stream.Collectors;

public class CoverageAdapterAgent {
    private static final Logger logger = LoggerFactory.getLogger(CoverageAdapterAgent.class);

    private final String rabbitmqUrl;
    private final int flushInterval;
    private final String jacocoAddress;
    private final int jacocoPort;
    private final String jacocoCliJar;
    private final String jacocoExecFile;
    private final String jacocoClassfiles;
    private final Path fingerprintFile;

    private final JaCoCoClient jacocoClient;
    private final RabbitMQPublisher mqPublisher;
    private final GitInfoCollector gitInfoCollector;
    private final FingerprintCalculator fingerprintCalculator;

    private ScheduledExecutorService scheduler;
    private String lastFingerprint;
    private boolean running = false;

    public CoverageAdapterAgent(
            String rabbitmqUrl,
            int flushInterval,
            String jacocoAddress,
            int jacocoPort,
            String jacocoCliJar,
            String jacocoExecFile,
            String jacocoClassfiles,
            String fingerprintFile) {
        this.rabbitmqUrl = rabbitmqUrl;
        this.flushInterval = flushInterval;
        this.jacocoAddress = jacocoAddress;
        this.jacocoPort = jacocoPort;
        this.jacocoCliJar = jacocoCliJar;
        this.jacocoExecFile = jacocoExecFile;
        this.jacocoClassfiles = jacocoClassfiles;
        
        // Expand user home directory
        String expandedFingerprintFile = fingerprintFile.replaceFirst("^~", System.getProperty("user.home"));
        this.fingerprintFile = Paths.get(expandedFingerprintFile);

        // Initialize components
        this.jacocoClient = new JaCoCoClient(jacocoCliJar, jacocoAddress, jacocoPort, jacocoExecFile, jacocoClassfiles);
        this.mqPublisher = new RabbitMQPublisher(rabbitmqUrl);
        this.gitInfoCollector = new GitInfoCollector();
        this.fingerprintCalculator = new FingerprintCalculator();

        // Load last fingerprint
        this.lastFingerprint = loadFingerprint();

        logger.info("CoverageAdapterAgent initialized");
        logger.info("  RabbitMQ URL: {}", rabbitmqUrl);
        logger.info("  Flush interval: {}s", flushInterval);
        logger.info("  JaCoCo address: {}:{}", jacocoAddress, jacocoPort);
        logger.info("  JaCoCo CLI jar: {}", jacocoCliJar);
        logger.info("  JaCoCo exec file: {}", jacocoExecFile);
        logger.info("  JaCoCo classfiles: {}", jacocoClassfiles);
        logger.info("  Fingerprint file: {}", this.fingerprintFile);
    }

    public void start() {
        if (running) {
            logger.warn("Agent already running");
            return;
        }

        running = true;
        scheduler = Executors.newScheduledThreadPool(1);

        // Report on startup (without checking fingerprint)
        logger.info("Reporting coverage on startup...");
        try {
            Thread.sleep(1000); // Wait a bit to ensure JaCoCo agent has data
            reportCoverageOnStartup();
        } catch (Exception e) {
            logger.error("Error reporting coverage on startup", e);
        }

        // Schedule periodic collection
        scheduler.scheduleAtFixedRate(
                this::flushCoverage,
                flushInterval,
                flushInterval,
                TimeUnit.SECONDS
        );

        logger.info("CoverageAdapterAgent started, will collect coverage every {} seconds", flushInterval);
    }

    public void stop() {
        if (!running) {
            return;
        }

        running = false;
        if (scheduler != null) {
            scheduler.shutdown();
            try {
                if (!scheduler.awaitTermination(5, TimeUnit.SECONDS)) {
                    scheduler.shutdownNow();
                }
            } catch (InterruptedException e) {
                scheduler.shutdownNow();
                Thread.currentThread().interrupt();
            }
        }

        if (mqPublisher != null) {
            mqPublisher.close();
        }

        logger.info("CoverageAdapterAgent stopped");
    }

    private void reportCoverageOnStartup() {
        try {
            CoverageData coverageData = collectCoverageData();
            
            int totalRanges = coverageData.getFileRanges().values().stream()
                    .mapToInt(List::size)
                    .sum();
            logger.info("Coverage data collected: {} files, {} total ranges", 
                    coverageData.getFileRanges().size(), totalRanges);

            // Calculate fingerprint
            Map<String, List<CoverageRange>> ranges = coverageData.getFileRanges();
            String currentFingerprint = fingerprintCalculator.calculate(ranges);
            logger.info("Coverage fingerprint: {}", currentFingerprint);

            // Report coverage
            reportCoverage(coverageData);

            // Update fingerprint
            lastFingerprint = currentFingerprint;
            saveFingerprint(currentFingerprint);

        } catch (Exception e) {
            logger.error("Error reporting coverage on startup", e);
        }
    }

    private void flushCoverage() {
        try {
            CoverageData coverageData = collectCoverageData();

            // Extract executed lines and compress to ranges
            Map<String, List<Integer>> executedLines = extractExecutedLines(coverageData);
            Map<String, List<CoverageRange>> ranges = compressToRanges(executedLines);

            // Calculate fingerprint
            String currentFingerprint = fingerprintCalculator.calculate(ranges);

            // Check if coverage has changed
            if (currentFingerprint.equals(lastFingerprint) && !lastFingerprint.isEmpty()) {
                logger.info("Coverage unchanged (fingerprint match), skipping report");
                return;
            }

            logger.info("Coverage changed (fingerprint mismatch), reporting to MQ");
            logger.debug("Coverage fingerprint: current={}, last={}", currentFingerprint, lastFingerprint);

            // Report coverage
            reportCoverage(coverageData);

            // Update fingerprint
            lastFingerprint = currentFingerprint;
            saveFingerprint(currentFingerprint);

        } catch (Exception e) {
            logger.error("Error flushing coverage", e);
        }
    }

    private CoverageData collectCoverageData() {
        // Dump coverage data
        if (!jacocoClient.dump()) {
            logger.warn("Failed to dump coverage data, returning empty coverage");
            return new CoverageData();
        }

        // Generate XML report
        String xmlContent = jacocoClient.report();
        if (xmlContent == null || xmlContent.isEmpty()) {
            logger.warn("Failed to generate XML report, returning empty coverage");
            return new CoverageData();
        }

        // Parse XML
        return jacocoClient.parseXml(xmlContent);
    }

    private Map<String, List<Integer>> extractExecutedLines(CoverageData coverageData) {
        Map<String, List<Integer>> executedLines = new HashMap<>();

        for (Map.Entry<String, List<CoverageRange>> entry : coverageData.getFileRanges().entrySet()) {
            String filePath = entry.getKey();
            List<Integer> lines = new ArrayList<>();

            for (CoverageRange range : entry.getValue()) {
                if (range.getHit() > 0) {
                    // Add all lines in the range
                    for (int lineNum = range.getStartLine(); lineNum <= range.getEndLine(); lineNum++) {
                        lines.add(lineNum);
                    }
                }
            }

            executedLines.put(filePath, lines.stream().sorted().distinct().collect(Collectors.toList()));
        }

        return executedLines;
    }

    private Map<String, List<CoverageRange>> compressToRanges(Map<String, List<Integer>> executedLines) {
        Map<String, List<CoverageRange>> ranges = new HashMap<>();

        for (Map.Entry<String, List<Integer>> entry : executedLines.entrySet()) {
            String filePath = entry.getKey();
            List<Integer> lines = entry.getValue();

            if (lines.isEmpty()) {
                continue;
            }

            List<CoverageRange> fileRanges = new ArrayList<>();
            int start = lines.get(0);
            int end = lines.get(0);

            for (int i = 1; i < lines.size(); i++) {
                int line = lines.get(i);
                if (line == end + 1) {
                    // Consecutive, extend range
                    end = line;
                } else {
                    // Not consecutive, save current range and start new one
                    fileRanges.add(new CoverageRange(filePath, start, 0, end, 0, end - start + 1, 1));
                    start = line;
                    end = line;
                }
            }

            // Save last range
            fileRanges.add(new CoverageRange(filePath, start, 0, end, 0, end - start + 1, 1));
            ranges.put(filePath, fileRanges);
        }

        return ranges;
    }

    private void reportCoverage(CoverageData coverageData) {
        if (rabbitmqUrl == null || rabbitmqUrl.isEmpty()) {
            logger.warn("RabbitMQ URL not configured, skipping report");
            return;
        }

        try {
            // Get Git info
            GitInfo gitInfo = gitInfoCollector.collect();

            // Format coverage data
            String coverageRaw = formatCoverageRaw(coverageData);

            if (coverageRaw == null || coverageRaw.trim().equals("mode: count")) {
                logger.warn("Coverage data is empty, skipping report");
                return;
            }

            // Create report message
            Map<String, Object> report = new HashMap<>();
            report.put("repo", gitInfo.getRepo());
            report.put("repo_id", gitInfo.getRepoId());
            report.put("branch", gitInfo.getBranch());
            report.put("commit", gitInfo.getCommit());

            Map<String, Object> ci = new HashMap<>();
            ci.put("provider", gitInfo.getCiProvider());
            ci.put("pipeline_id", gitInfo.getCiPipelineId());
            ci.put("job_id", gitInfo.getCiJobId());
            report.put("ci", ci);

            Map<String, Object> coverage = new HashMap<>();
            coverage.put("format", "jacoco");
            coverage.put("raw", coverageRaw);
            report.put("coverage", coverage);

            report.put("timestamp", System.currentTimeMillis() / 1000);

            // Publish to RabbitMQ
            mqPublisher.publish(report);

            logger.info("Successfully published coverage report: repo={}, repo_id={}, branch={}, commit={}",
                    gitInfo.getRepo(), gitInfo.getRepoId(), gitInfo.getBranch(), gitInfo.getCommit());

        } catch (Exception e) {
            logger.error("Error reporting coverage", e);
        }
    }

    private String formatCoverageRaw(CoverageData coverageData) {
        List<String> lines = new ArrayList<>();
        lines.add("mode: count");

        List<String> sortedFiles = new ArrayList<>(coverageData.getFileRanges().keySet());
        Collections.sort(sortedFiles);

        for (String filePath : sortedFiles) {
            List<CoverageRange> ranges = coverageData.getFileRanges().get(filePath);
            for (CoverageRange range : ranges) {
                String line = String.format("%s:%d.%d,%d.%d %d %d",
                        filePath,
                        range.getStartLine(), range.getStartCol(),
                        range.getEndLine(), range.getEndCol(),
                        range.getStatements(),
                        range.getHit());
                lines.add(line);
            }
        }

        return String.join("\n", lines);
    }

    private String loadFingerprint() {
        try {
            if (Files.exists(fingerprintFile)) {
                return Files.readString(fingerprintFile).trim();
            }
        } catch (Exception e) {
            logger.warn("Failed to load fingerprint: {}", e.getMessage());
        }
        return "";
    }

    private void saveFingerprint(String fingerprint) {
        try {
            Files.createDirectories(fingerprintFile.getParent());
            Files.writeString(fingerprintFile, fingerprint);
        } catch (Exception e) {
            logger.error("Failed to save fingerprint: {}", e.getMessage());
        }
    }
}

