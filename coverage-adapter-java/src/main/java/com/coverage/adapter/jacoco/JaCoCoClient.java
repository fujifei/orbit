package com.coverage.adapter.jacoco;

import com.coverage.adapter.model.CoverageData;
import com.coverage.adapter.model.CoverageRange;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.NodeList;

import org.xml.sax.EntityResolver;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.*;

public class JaCoCoClient {
    private static final Logger logger = LoggerFactory.getLogger(JaCoCoClient.class);

    private final String jacocoCliJar;
    private final String jacocoAddress;
    private final int jacocoPort;
    private final String jacocoExecFile;
    private final String jacocoClassfiles;

    public JaCoCoClient(String jacocoCliJar, String jacocoAddress, int jacocoPort, 
                       String jacocoExecFile, String jacocoClassfiles) {
        this.jacocoCliJar = jacocoCliJar;
        this.jacocoAddress = jacocoAddress;
        this.jacocoPort = jacocoPort;
        this.jacocoExecFile = jacocoExecFile;
        this.jacocoClassfiles = jacocoClassfiles;
    }

    /**
     * Execute jacoco dump command to get coverage data
     * @return true if successful, false otherwise
     */
    public boolean dump() {
        try {
            List<String> command = new ArrayList<>();
            command.add("java");
            command.add("-jar");
            command.add(jacocoCliJar);
            command.add("dump");
            command.add("--address");
            command.add(jacocoAddress);
            command.add("--port");
            command.add(String.valueOf(jacocoPort));
            command.add("--destfile");
            command.add(jacocoExecFile);

            logger.debug("Executing: {}", String.join(" ", command));

            ProcessBuilder pb = new ProcessBuilder(command);
            pb.redirectErrorStream(true);
            Process process = pb.start();

            // Read output
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                logger.error("jacococli dump failed with exit code {}: {}", exitCode, output);
                return false;
            }

            Path execPath = Paths.get(jacocoExecFile);
            if (!Files.exists(execPath)) {
                logger.warn("jacoco.exec file not created: {}", jacocoExecFile);
                return false;
            }

            logger.debug("Successfully dumped coverage data to {}", jacocoExecFile);
            return true;

        } catch (Exception e) {
            logger.error("Error executing jacococli dump", e);
            return false;
        }
    }

    /**
     * Execute jacoco report command to generate XML report
     * @return XML content as string, or null if failed
     */
    public String report() {
        Path tempXmlFile = null;
        try {
            // Create temporary XML file
            tempXmlFile = Files.createTempFile("jacoco-report-", ".xml");

            List<String> command = new ArrayList<>();
            command.add("java");
            command.add("-jar");
            command.add(jacocoCliJar);
            command.add("report");
            command.add(jacocoExecFile);
            command.add("--classfiles");
            command.add(jacocoClassfiles);
            command.add("--xml");
            command.add(tempXmlFile.toString());

            logger.debug("Executing: {}", String.join(" ", command));

            ProcessBuilder pb = new ProcessBuilder(command);
            pb.redirectErrorStream(true);
            Process process = pb.start();

            // Read output
            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }

            int exitCode = process.waitFor();
            if (exitCode != 0) {
                logger.error("jacococli report failed with exit code {}: {}", exitCode, output);
                return null;
            }

            // Read XML content
            String xmlContent = Files.readString(tempXmlFile);
            return xmlContent;

        } catch (Exception e) {
            logger.error("Error executing jacococli report", e);
            return null;
        } finally {
            // Clean up temporary file
            if (tempXmlFile != null) {
                try {
                    Files.deleteIfExists(tempXmlFile);
                } catch (IOException e) {
                    logger.warn("Failed to delete temporary XML file: {}", e.getMessage());
                }
            }
        }
    }

    /**
     * Parse XML coverage report
     * @param xmlContent XML content as string
     * @return CoverageData object
     */
    public CoverageData parseXml(String xmlContent) {
        CoverageData coverageData = new CoverageData();
        Map<String, List<CoverageRange>> fileRanges = new HashMap<>();

        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            // Disable DTD validation to avoid FileNotFoundException for report.dtd
            factory.setValidating(false);
            factory.setFeature("http://apache.org/xml/features/nonvalidating/load-dtd-grammar", false);
            factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            
            DocumentBuilder builder = factory.newDocumentBuilder();
            // Set EntityResolver to ignore external DTD files
            builder.setEntityResolver(new EntityResolver() {
                @Override
                public InputSource resolveEntity(String publicId, String systemId) throws SAXException, IOException {
                    // Return empty input source to ignore DTD files
                    return new InputSource(new ByteArrayInputStream("<?xml version='1.0' encoding='UTF-8'?>".getBytes()));
                }
            });
            
            Document doc = builder.parse(new ByteArrayInputStream(xmlContent.getBytes("UTF-8")));

            // Get all packages
            NodeList packages = doc.getElementsByTagName("package");
            for (int i = 0; i < packages.getLength(); i++) {
                Element packageElement = (Element) packages.item(i);
                String packageName = packageElement.getAttribute("name");

                // Get all sourcefiles in this package
                NodeList sourcefiles = packageElement.getElementsByTagName("sourcefile");
                for (int j = 0; j < sourcefiles.getLength(); j++) {
                    Element sourcefileElement = (Element) sourcefiles.item(j);
                    String sourceFileName = sourcefileElement.getAttribute("name");

                    if (sourceFileName == null || sourceFileName.isEmpty()) {
                        continue;
                    }

                    // Build file path
                    String filePath;
                    if (packageName != null && !packageName.isEmpty()) {
                        filePath = packageName.replace('.', '/') + "/" + sourceFileName;
                    } else {
                        filePath = sourceFileName;
                    }

                    // Collect covered lines
                    List<Integer> coveredLines = new ArrayList<>();
                    NodeList lines = sourcefileElement.getElementsByTagName("line");
                    for (int k = 0; k < lines.getLength(); k++) {
                        Element lineElement = (Element) lines.item(k);
                        String lineNumStr = lineElement.getAttribute("nr");
                        if (lineNumStr == null || lineNumStr.isEmpty()) {
                            continue;
                        }

                        try {
                            int lineNum = Integer.parseInt(lineNumStr);
                            String miStr = lineElement.getAttribute("mi");
                            String ciStr = lineElement.getAttribute("ci");
                            int mi = miStr != null && !miStr.isEmpty() ? Integer.parseInt(miStr) : 0;
                            int ci = ciStr != null && !ciStr.isEmpty() ? Integer.parseInt(ciStr) : 0;

                            if (ci > 0) {
                                // This line is covered
                                coveredLines.add(lineNum);
                            }
                        } catch (NumberFormatException e) {
                            logger.warn("Failed to parse line number: {}", lineNumStr);
                        }
                    }

                    // Convert covered lines to ranges
                    if (!coveredLines.isEmpty()) {
                        // Sort and deduplicate
                        coveredLines = new ArrayList<>(new TreeSet<>(coveredLines));
                        List<CoverageRange> ranges = compressLinesToRanges(filePath, coveredLines);
                        fileRanges.put(filePath, ranges);
                    }
                }
            }

            coverageData.setFileRanges(fileRanges);
            return coverageData;

        } catch (Exception e) {
            logger.error("Error parsing XML coverage", e);
            return coverageData;
        }
    }

    private List<CoverageRange> compressLinesToRanges(String filePath, List<Integer> lines) {
        List<CoverageRange> ranges = new ArrayList<>();
        if (lines.isEmpty()) {
            return ranges;
        }

        int start = lines.get(0);
        int end = lines.get(0);

        for (int i = 1; i < lines.size(); i++) {
            int line = lines.get(i);
            if (line == end + 1) {
                // Consecutive, extend range
                end = line;
            } else {
                // Not consecutive, save current range and start new one
                int statements = end - start + 1;
                ranges.add(new CoverageRange(filePath, start, 0, end, 0, statements, 1));
                start = line;
                end = line;
            }
        }

        // Save last range
        int statements = end - start + 1;
        ranges.add(new CoverageRange(filePath, start, 0, end, 0, statements, 1));

        return ranges;
    }
}

