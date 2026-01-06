package com.coverage.adapter.git;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.net.HttpURLConnection;
import java.net.URL;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class GitInfoCollector {
    private static final Logger logger = LoggerFactory.getLogger(GitInfoCollector.class);
    private static final Map<String, String> repoIdCache = new HashMap<>();
    private static final Path repoIdCacheFile;
    
    static {
        // Initialize cache file path
        String cacheFileStr = System.getenv("COVERAGE_ADAPTER_REPO_ID_CACHE_FILE");
        if (cacheFileStr == null || cacheFileStr.isEmpty()) {
            cacheFileStr = System.getProperty("user.home") + "/.coverage_adapter_repo_id_cache";
        }
        repoIdCacheFile = Paths.get(cacheFileStr);
        
        // Load cache on startup
        loadRepoIdCache();
    }

    public GitInfo collect() {
        GitInfo gitInfo = new GitInfo();

        try {
            String cwd = System.getProperty("user.dir");

            // Get git remote origin
            String repoUrl = executeGitCommand(cwd, "config", "--get", "remote.origin.url");
            if (repoUrl != null && !repoUrl.isEmpty()) {
                gitInfo.setRepo(repoUrl.trim());
                gitInfo.setRepoId(getRepoId(repoUrl.trim()));
            }

            // Get current branch
            String branch = executeGitCommand(cwd, "rev-parse", "--abbrev-ref", "HEAD");
            if (branch != null && !branch.isEmpty()) {
                gitInfo.setBranch(branch.trim());
            }

            // Get current commit
            String commit = executeGitCommand(cwd, "rev-parse", "HEAD");
            if (commit != null && !commit.isEmpty()) {
                gitInfo.setCommit(commit.trim());
            }

            // Get CI info
            collectCiInfo(gitInfo);

        } catch (Exception e) {
            logger.warn("Failed to collect git info: {}", e.getMessage());
        }

        return gitInfo;
    }

    private String executeGitCommand(String cwd, String... args) {
        try {
            ProcessBuilder pb = new ProcessBuilder();
            pb.command("git");
            for (String arg : args) {
                pb.command().add(arg);
            }
            pb.directory(Paths.get(cwd).toFile());
            pb.redirectErrorStream(true);

            Process process = pb.start();
            StringBuilder output = new StringBuilder();

            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }

            int exitCode = process.waitFor();
            if (exitCode == 0) {
                return output.toString().trim();
            }

        } catch (Exception e) {
            logger.debug("Failed to execute git command: {}", e.getMessage());
        }

        return null;
    }

    private String getRepoId(String repoUrl) {
        // Check in-memory cache first
        if (repoIdCache.containsKey(repoUrl)) {
            logger.debug("Using cached repo_id from memory for: {}", repoUrl);
            return repoIdCache.get(repoUrl);
        }

        // Try to get repo_id from GitHub API first
        String repoId = getGitHubRepoId(repoUrl);
        
        // If GitHub API fails, fallback to SHA256 hash
        if (repoId == null || repoId.isEmpty()) {
            logger.debug("GitHub API failed or not a GitHub repo, falling back to SHA256 hash");
            repoId = calculateSha256Hash(repoUrl);
        }
        
        // Cache the result (both in-memory and persistent)
        if (repoId != null && !repoId.isEmpty()) {
            repoIdCache.put(repoUrl, repoId);
            saveRepoIdCache(repoUrl, repoId);
        }
        
        return repoId != null ? repoId : "";
    }

    private String getGitHubRepoId(String repoUrl) {
        try {
            // Parse owner and repo from URL
            String[] ownerRepo = parseGitHubRepoUrl(repoUrl);
            if (ownerRepo == null) {
                logger.debug("Not a GitHub repository URL: {}", repoUrl);
                return null;
            }
            
            String owner = ownerRepo[0];
            String repo = ownerRepo[1];
            logger.debug("Parsed GitHub repo URL - owner: {}, repo: {}", owner, repo);
            
            // Build GitHub API URL
            String apiUrl = String.format("https://api.github.com/repos/%s/%s", owner, repo);
            logger.debug("Calling GitHub API: {}", apiUrl);
            
            // Create HTTP connection
            URL url = new URL(apiUrl);
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "coverage-adapter");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            
            // Support GitHub token authentication (from environment variable)
            String githubToken = System.getenv("GITHUB_TOKEN");
            if (githubToken == null || githubToken.isEmpty()) {
                githubToken = System.getenv("COVERAGE_ADAPTER_GITHUB_TOKEN");
            }
            if (githubToken != null && !githubToken.isEmpty()) {
                conn.setRequestProperty("Authorization", "token " + githubToken);
                logger.debug("Using GitHub token for authentication (higher rate limit)");
            } else {
                logger.debug("No GitHub token found, using unauthenticated request (lower rate limit)");
            }
            
            // Make request
            int responseCode = conn.getResponseCode();
            if (responseCode == HttpURLConnection.HTTP_OK) {
                // Parse JSON response
                ObjectMapper mapper = new ObjectMapper();
                JsonNode jsonNode = mapper.readTree(conn.getInputStream());
                long repoIdLong = jsonNode.get("id").asLong();
                String repoId = String.valueOf(repoIdLong);
                logger.info("Successfully retrieved repo_id from GitHub API: {} for {}/{}", repoId, owner, repo);
                return repoId;
            } else {
                logger.warn("GitHub API returned non-200 status: {} for URL: {}", responseCode, apiUrl);
                return null;
            }
        } catch (Exception e) {
            logger.debug("Failed to get GitHub repo ID: {}", e.getMessage());
            return null;
        }
    }

    private String[] parseGitHubRepoUrl(String repoUrl) {
        if (repoUrl == null || repoUrl.isEmpty()) {
            return null;
        }
        
        // Remove .git suffix if present
        String cleanedUrl = repoUrl.replaceAll("\\.git$", "").trim();
        
        // Patterns to match:
        // 1. https://github.com/owner/repo
        // 2. git@github.com:owner/repo
        // 3. git://github.com/owner/repo
        Pattern[] patterns = {
            Pattern.compile("(?i)^https?://github\\.com/([^/]+)/([^/]+)/?$"),
            Pattern.compile("(?i)^git@github\\.com:([^/]+)/([^/]+)/?$"),
            Pattern.compile("(?i)^git://github\\.com/([^/]+)/([^/]+)/?$")
        };
        
        for (Pattern pattern : patterns) {
            Matcher matcher = pattern.matcher(cleanedUrl);
            if (matcher.matches()) {
                return new String[]{matcher.group(1), matcher.group(2)};
            }
        }
        
        // Try manual parsing for common formats
        if (cleanedUrl.contains("github.com")) {
            String[] parts = cleanedUrl.split("github.com");
            if (parts.length > 1) {
                String path = parts[1].replaceAll("^[/:]", "").replaceAll("/$", "");
                String[] pathParts = path.split("/");
                if (pathParts.length >= 2) {
                    return new String[]{pathParts[0], pathParts[1]};
                }
            }
        }
        
        return null;
    }

    private String calculateSha256Hash(String repoUrl) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hash = digest.digest(repoUrl.getBytes("UTF-8"));
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
            logger.error("Failed to calculate SHA256 hash for repo_id", e);
            return "";
        }
    }

    /**
     * Load repo_id cache from file
     */
    private static void loadRepoIdCache() {
        try {
            if (Files.exists(repoIdCacheFile)) {
                ObjectMapper mapper = new ObjectMapper();
                Map<String, String> cache = mapper.readValue(
                    repoIdCacheFile.toFile(),
                    new TypeReference<Map<String, String>>() {}
                );
                repoIdCache.putAll(cache);
                logger.info("Loaded {} repo_id entries from cache file: {}", 
                    cache.size(), repoIdCacheFile);
            } else {
                logger.debug("Repo_id cache file does not exist: {}", repoIdCacheFile);
            }
        } catch (Exception e) {
            logger.warn("Failed to load repo_id cache from file: {}", e.getMessage());
        }
    }

    /**
     * Save repo_id to cache file
     * Only saves if the repo_id is new or changed
     */
    private static void saveRepoIdCache(String repoUrl, String repoId) {
        try {
            // Check if repo_id already exists and is the same
            String existingRepoId = repoIdCache.get(repoUrl);
            if (existingRepoId != null && existingRepoId.equals(repoId)) {
                // Already cached, no need to save
                return;
            }
            
            // Ensure parent directory exists
            if (repoIdCacheFile.getParent() != null) {
                Files.createDirectories(repoIdCacheFile.getParent());
            }
            
            // Write entire cache to file
            ObjectMapper mapper = new ObjectMapper();
            mapper.writerWithDefaultPrettyPrinter().writeValue(
                repoIdCacheFile.toFile(),
                repoIdCache
            );
            logger.debug("Cached repo_id for {}: {} (saved to file)", repoUrl, repoId);
        } catch (Exception e) {
            logger.warn("Failed to save repo_id cache to file: {}", e.getMessage());
        }
    }

    private void collectCiInfo(GitInfo gitInfo) {
        // GitLab CI
        String pipelineId = System.getenv("CI_PIPELINE_ID");
        if (pipelineId != null && !pipelineId.isEmpty()) {
            gitInfo.setCiProvider("gitlab");
            gitInfo.setCiPipelineId(pipelineId);
            gitInfo.setCiJobId(System.getenv("CI_JOB_ID"));
            return;
        }

        // Jenkins
        String buildNumber = System.getenv("BUILD_NUMBER");
        if (buildNumber != null && !buildNumber.isEmpty()) {
            gitInfo.setCiProvider("jenkins");
            gitInfo.setCiPipelineId(buildNumber);
            gitInfo.setCiJobId(System.getenv("JOB_NAME"));
            return;
        }

        // GitHub Actions
        String runId = System.getenv("GITHUB_RUN_ID");
        if (runId != null && !runId.isEmpty()) {
            gitInfo.setCiProvider("github");
            gitInfo.setCiPipelineId(runId);
            gitInfo.setCiJobId(System.getenv("GITHUB_JOB"));
            return;
        }

        // CircleCI
        String buildNum = System.getenv("CIRCLE_BUILD_NUM");
        if (buildNum != null && !buildNum.isEmpty()) {
            gitInfo.setCiProvider("circleci");
            gitInfo.setCiPipelineId(buildNum);
            gitInfo.setCiJobId(System.getenv("CIRCLE_JOB"));
            return;
        }
    }
}

