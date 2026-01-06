package com.coverage.adapter.util;

import com.coverage.adapter.model.CoverageRange;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

public class FingerprintCalculator {
    private static final Logger logger = LoggerFactory.getLogger(FingerprintCalculator.class);

    /**
     * Calculate fingerprint from coverage ranges
     * @param ranges Map of file path to list of coverage ranges
     * @return SHA256 hash as hex string
     */
    public String calculate(Map<String, List<CoverageRange>> ranges) {
        try {
            List<String> parts = new ArrayList<>();

            // Sort filenames for consistency
            List<String> filenames = new ArrayList<>(ranges.keySet());
            Collections.sort(filenames);

            for (String filename : filenames) {
                List<CoverageRange> fileRanges = ranges.get(filename);
                if (fileRanges == null || fileRanges.isEmpty()) {
                    continue;
                }

                // Build range strings
                List<String> rangeStrs = new ArrayList<>();
                for (CoverageRange range : fileRanges) {
                    rangeStrs.add(String.format("%d-%d", range.getStartLine(), range.getEndLine()));
                }

                parts.add(String.format("%s:%s", filename, String.join(",", rangeStrs)));
            }

            String content = String.join(";", parts);

            // Calculate SHA256 hash
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(content.getBytes(StandardCharsets.UTF_8));
            StringBuilder hexString = new StringBuilder();
            for (byte b : hash) {
                String hex = Integer.toHexString(0xff & b);
                if (hex.length() == 1) {
                    hexString.append('0');
                }
                hexString.append(hex);
            }

            return hexString.toString();

        } catch (Exception e) {
            logger.error("Failed to calculate fingerprint", e);
            return "";
        }
    }
}

