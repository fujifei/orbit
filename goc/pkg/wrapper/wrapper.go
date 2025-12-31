/*
 Copyright 2020 Qiniu Cloud (qiniu.com)

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
*/

package wrapper

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/qiniu/goc/pkg/cover"
	log "github.com/sirupsen/logrus"
	"github.com/streadway/amqp"
)

// CoverageReportMessage represents the structured coverage data for RabbitMQ
type CoverageReportMessage struct {
	Repo      string       `json:"repo"`
	RepoID    string       `json:"repo_id"`
	Branch    string       `json:"branch"`
	Commit    string       `json:"commit"`
	CI        CIMetadata   `json:"ci"`
	Coverage  CoverageData `json:"coverage"`
	Timestamp int64        `json:"timestamp"`
}

// CIMetadata contains CI information
type CIMetadata struct {
	Provider   string `json:"provider"`
	PipelineID string `json:"pipeline_id"`
	JobID      string `json:"job_id"`
}

// CoverageData contains coverage format and raw data
type CoverageData struct {
	Format string `json:"format"`
	Raw    string `json:"raw"`
}

// GocServerInterface defines the interface for goc server
type GocServerInterface interface {
	Route(w io.Writer) *gin.Engine
	Run(port string)
}

// Wrapper wraps goc server and adds structured data reporting
type Wrapper struct {
	gocServer    GocServerInterface
	gocServerURL string
	rabbitMQURL  string
	rabbitMQConn *amqp.Connection
	rabbitMQCh   *amqp.Channel
	gitInfo      *GitInfo
	ciInfo       *CIMetadata
}

// GitInfo contains git repository information
type GitInfo struct {
	Repo   string
	RepoID string
	Branch string
	Commit string
}

// NewWrapper creates a new wrapper instance
func NewWrapper(gocServer GocServerInterface, rabbitMQURL string) (*Wrapper, error) {
	// Get git information
	gitInfo, err := GetGitInfo()
	if err != nil {
		log.Warnf("Failed to get git info: %v, using empty values", err)
		gitInfo = &GitInfo{}
	}

	// Get CI information
	ciInfo := GetCIInfo()

	wrapper := &Wrapper{
		gocServer:   gocServer,
		rabbitMQURL: rabbitMQURL,
		gitInfo:     gitInfo,
		ciInfo:      ciInfo,
	}

	// Connect to RabbitMQ if URL is provided
	if rabbitMQURL != "" {
		if err := wrapper.connectRabbitMQ(); err != nil {
			return nil, fmt.Errorf("failed to connect to RabbitMQ: %v", err)
		}
	}

	return wrapper, nil
}

// GetCIInfo retrieves CI information from environment variables
func GetCIInfo() *CIMetadata {
	ciInfo := &CIMetadata{}

	// GitLab CI
	if pipelineID := os.Getenv("CI_PIPELINE_ID"); pipelineID != "" {
		ciInfo.Provider = "gitlab"
		ciInfo.PipelineID = pipelineID
		if jobID := os.Getenv("CI_JOB_ID"); jobID != "" {
			ciInfo.JobID = jobID
		}
		return ciInfo
	}

	// Jenkins
	if buildNumber := os.Getenv("BUILD_NUMBER"); buildNumber != "" {
		ciInfo.Provider = "jenkins"
		ciInfo.PipelineID = buildNumber
		if jobName := os.Getenv("JOB_NAME"); jobName != "" {
			ciInfo.JobID = jobName
		}
		return ciInfo
	}

	// GitHub Actions
	if runID := os.Getenv("GITHUB_RUN_ID"); runID != "" {
		ciInfo.Provider = "github"
		ciInfo.PipelineID = runID
		if jobID := os.Getenv("GITHUB_JOB"); jobID != "" {
			ciInfo.JobID = jobID
		}
		return ciInfo
	}

	// CircleCI
	if buildNum := os.Getenv("CIRCLE_BUILD_NUM"); buildNum != "" {
		ciInfo.Provider = "circleci"
		ciInfo.PipelineID = buildNum
		if jobNum := os.Getenv("CIRCLE_JOB"); jobNum != "" {
			ciInfo.JobID = jobNum
		}
		return ciInfo
	}

	// Default: no CI detected
	return ciInfo
}

// connectRabbitMQ connects to RabbitMQ
func (w *Wrapper) connectRabbitMQ() error {
	conn, err := amqp.Dial(w.rabbitMQURL)
	if err != nil {
		return err
	}
	w.rabbitMQConn = conn

	ch, err := conn.Channel()
	if err != nil {
		conn.Close()
		return err
	}
	w.rabbitMQCh = ch

	// Declare exchange
	err = ch.ExchangeDeclare(
		"coverage_exchange",
		"topic",
		true,
		false,
		false,
		false,
		nil,
	)
	if err != nil {
		ch.Close()
		conn.Close()
		return err
	}

	log.Infof("Connected to RabbitMQ: %s", w.rabbitMQURL)
	return nil
}

// Close closes RabbitMQ connection
func (w *Wrapper) Close() {
	if w.rabbitMQCh != nil {
		w.rabbitMQCh.Close()
	}
	if w.rabbitMQConn != nil {
		w.rabbitMQConn.Close()
	}
}

// GetGitInfo retrieves git repository information
func GetGitInfo() (*GitInfo, error) {
	gitInfo := &GitInfo{}

	// Get current working directory
	wd, err := os.Getwd()
	if err != nil {
		return nil, fmt.Errorf("failed to get working directory: %v", err)
	}

	// Find .git directory
	gitDir, err := findGitDir(wd)
	if err != nil {
		return nil, fmt.Errorf("failed to find .git directory: %v", err)
	}

	// Get repo URL (remote origin)
	if repo, err := getGitRemoteOrigin(gitDir); err == nil {
		gitInfo.Repo = repo
		log.Infof("Successfully retrieved git repo: %s", repo)
		// Get repo_id from GitHub API
		if repoID, err := getGitHubRepoID(repo); err == nil {
			gitInfo.RepoID = repoID
			log.Infof("Successfully retrieved git repo_id: %s", repoID)
		} else {
			log.Warnf("Failed to get GitHub repo ID: %v", err)
		}
	} else {
		log.Warnf("Failed to get git remote origin: %v", err)
	}

	// Get current branch
	if branch, err := getGitBranch(gitDir); err == nil {
		gitInfo.Branch = branch
		log.Infof("Successfully retrieved git branch: %s", branch)
	} else {
		log.Warnf("Failed to get git branch: %v", err)
	}

	// Get current commit
	if commit, err := getGitCommit(gitDir); err == nil {
		gitInfo.Commit = commit
		log.Infof("Successfully retrieved git commit: %s", commit)
	} else {
		log.Warnf("Failed to get git commit: %v", err)
	}

	return gitInfo, nil
}

// findGitDir finds the .git directory by traversing up the directory tree
func findGitDir(startDir string) (string, error) {
	dir := startDir
	for {
		gitPath := filepath.Join(dir, ".git")
		if info, err := os.Stat(gitPath); err == nil && info.IsDir() {
			return gitPath, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return "", fmt.Errorf(".git directory not found")
		}
		dir = parent
	}
}

// getGitRemoteOrigin gets the remote origin URL
func getGitRemoteOrigin(gitDir string) (string, error) {
	configPath := filepath.Join(gitDir, "config")
	if _, err := os.Stat(configPath); os.IsNotExist(err) {
		return "", fmt.Errorf("git config not found")
	}

	data, err := ioutil.ReadFile(configPath)
	if err != nil {
		return "", err
	}

	// Parse git config to find remote origin URL
	lines := strings.Split(string(data), "\n")
	for i, line := range lines {
		if strings.TrimSpace(line) == "[remote \"origin\"]" {
			// Look for url in the next few lines
			for j := i + 1; j < len(lines) && j < i+10; j++ {
				if strings.HasPrefix(strings.TrimSpace(lines[j]), "url = ") {
					url := strings.TrimSpace(strings.TrimPrefix(lines[j], "url = "))
					return url, nil
				}
			}
		}
	}

	return "", fmt.Errorf("remote origin URL not found")
}

// getGitBranch gets the current branch name
func getGitBranch(gitDir string) (string, error) {
	// Try to read HEAD file
	headPath := filepath.Join(gitDir, "HEAD")
	if _, err := os.Stat(headPath); os.IsNotExist(err) {
		return "", fmt.Errorf("HEAD file not found")
	}

	data, err := ioutil.ReadFile(headPath)
	if err != nil {
		return "", err
	}

	headContent := strings.TrimSpace(string(data))
	if strings.HasPrefix(headContent, "ref: refs/heads/") {
		return strings.TrimPrefix(headContent, "ref: refs/heads/"), nil
	}

	// If HEAD is detached, try to get branch from git command
	cmd := exec.Command("git", "rev-parse", "--abbrev-ref", "HEAD")
	cmd.Dir = filepath.Dir(gitDir)
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(output)), nil
}

// getGitCommit gets the current commit hash
func getGitCommit(gitDir string) (string, error) {
	// Try to read HEAD file
	headPath := filepath.Join(gitDir, "HEAD")
	if _, err := os.Stat(headPath); os.IsNotExist(err) {
		return "", fmt.Errorf("HEAD file not found")
	}

	data, err := ioutil.ReadFile(headPath)
	if err != nil {
		return "", err
	}

	headContent := strings.TrimSpace(string(data))
	if strings.HasPrefix(headContent, "ref: ") {
		// Follow the ref
		refPath := strings.TrimPrefix(headContent, "ref: ")
		refFile := filepath.Join(gitDir, refPath)
		if commitData, err := ioutil.ReadFile(refFile); err == nil {
			return strings.TrimSpace(string(commitData)), nil
		}
	} else {
		// Detached HEAD, return the commit hash directly
		return headContent, nil
	}

	// Fallback to git command
	cmd := exec.Command("git", "rev-parse", "HEAD")
	cmd.Dir = filepath.Dir(gitDir)
	output, err := cmd.Output()
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(output)), nil
}

// parseGitHubRepoURL extracts owner and repo name from various git URL formats
func parseGitHubRepoURL(repoURL string) (owner, repo string, err error) {
	// Remove .git suffix if present
	repoURL = strings.TrimSuffix(repoURL, ".git")

	// Pattern 1: https://github.com/owner/repo
	// Pattern 2: git@github.com:owner/repo
	// Pattern 3: git://github.com/owner/repo
	patterns := []*regexp.Regexp{
		regexp.MustCompile(`(?i)^https?://github\.com/([^/]+)/([^/]+)/?$`),
		regexp.MustCompile(`(?i)^git@github\.com:([^/]+)/([^/]+)/?$`),
		regexp.MustCompile(`(?i)^git://github\.com/([^/]+)/([^/]+)/?$`),
	}

	for _, pattern := range patterns {
		matches := pattern.FindStringSubmatch(repoURL)
		if len(matches) == 3 {
			return matches[1], matches[2], nil
		}
	}

	return "", "", fmt.Errorf("unable to parse GitHub repo URL: %s", repoURL)
}

// GitHubRepoResponse represents the response from GitHub API
type GitHubRepoResponse struct {
	ID int64 `json:"id"`
}

// getGitHubRepoID fetches the repository ID from GitHub API
func getGitHubRepoID(repoURL string) (string, error) {
	// Parse owner and repo from URL
	owner, repo, err := parseGitHubRepoURL(repoURL)
	if err != nil {
		return "", err
	}
	log.Debugf("Parsed GitHub repo URL - owner: %s, repo: %s", owner, repo)

	// Build GitHub API URL
	apiURL := fmt.Sprintf("https://api.github.com/repos/%s/%s", owner, repo)
	log.Debugf("Calling GitHub API: %s", apiURL)

	// Create HTTP client with timeout
	client := &http.Client{
		Timeout: 10 * time.Second,
	}

	// Make request to GitHub API
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return "", fmt.Errorf("failed to create request: %v", err)
	}

	// Set User-Agent header (GitHub API requires this)
	req.Header.Set("User-Agent", "goc-wrapper")

	// Make the request
	resp, err := client.Do(req)
	if err != nil {
		log.Warnf("Failed to call GitHub API %s: %v", apiURL, err)
		return "", fmt.Errorf("failed to call GitHub API: %v", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		body, _ := ioutil.ReadAll(resp.Body)
		log.Warnf("GitHub API returned non-200 status: %d, body: %s", resp.StatusCode, string(body))
		return "", fmt.Errorf("GitHub API returned status %d: %s", resp.StatusCode, string(body))
	}

	// Parse JSON response
	var repoResponse GitHubRepoResponse
	if err := json.NewDecoder(resp.Body).Decode(&repoResponse); err != nil {
		return "", fmt.Errorf("failed to parse GitHub API response: %v", err)
	}

	// Convert ID to string
	repoID := strconv.FormatInt(repoResponse.ID, 10)
	log.Debugf("Successfully retrieved repo ID from GitHub API: %s", repoID)
	return repoID, nil
}

// Route sets up the wrapper routes
func (w *Wrapper) Route(writer io.Writer) *gin.Engine {
	if writer != nil {
		gin.DefaultWriter = writer
	}
	r := gin.Default()

	// Proxy all goc server routes except profile
	v1 := r.Group("/v1")
	{
		v1.POST("/cover/register", w.proxyToGocServer)
		v1.GET("/cover/profile", func(c *gin.Context) {
			w.handleProfile(c, false)
		})
		v1.POST("/cover/profile", func(c *gin.Context) {
			w.handleProfile(c, true)
		})
		v1.POST("/cover/clear", w.proxyToGocServer)
		v1.POST("/cover/init", w.proxyToGocServer)
		v1.GET("/cover/list", w.proxyToGocServer)
		v1.POST("/cover/remove", w.proxyToGocServer)
	}

	return r
}

// proxyToGocServer proxies a request to the internal goc server
func (w *Wrapper) proxyToGocServer(c *gin.Context) {
	// Read request body
	var bodyBytes []byte
	if c.Request.Body != nil {
		bodyBytes, _ = ioutil.ReadAll(c.Request.Body)
		c.Request.Body = ioutil.NopCloser(bytes.NewBuffer(bodyBytes))
	}

	// Create request to goc server
	url := w.gocServerURL + c.Request.RequestURI
	req, err := http.NewRequest(c.Request.Method, url, bytes.NewBuffer(bodyBytes))
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Copy headers
	for key, values := range c.Request.Header {
		for _, value := range values {
			req.Header.Add(key, value)
		}
	}

	// Make request
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}
	defer resp.Body.Close()

	// Copy response headers
	for key, values := range resp.Header {
		for _, value := range values {
			c.Writer.Header().Add(key, value)
		}
	}

	// Copy response body
	c.Writer.WriteHeader(resp.StatusCode)
	io.Copy(c.Writer, resp.Body)
}

// handleProfile handles profile requests and wraps the response
func (w *Wrapper) handleProfile(c *gin.Context, isPost bool) {
	// Get the original coverage data from goc server
	var coverageData []byte
	var err error

	if isPost {
		// POST request - need to forward the body
		var body cover.ProfileParam
		if err := c.ShouldBind(&body); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}

		// Call goc server's profile handler
		coverageData, err = w.getProfileFromGocServer(&body)
	} else {
		// GET request
		coverageData, err = w.getProfileFromGocServer(&cover.ProfileParam{})
	}

	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	// Create structured report
	report := CoverageReportMessage{
		Repo:   w.gitInfo.Repo,
		RepoID: w.gitInfo.RepoID,
		Branch: w.gitInfo.Branch,
		Commit: w.gitInfo.Commit,
		CI:     *w.ciInfo,
		Coverage: CoverageData{
			Format: "goc",
			Raw:    string(coverageData),
		},
		Timestamp: time.Now().Unix(),
	}

	// If RabbitMQ URL is provided, publish the report
	if w.rabbitMQURL != "" && w.rabbitMQCh != nil {
		if err := w.publishToRabbitMQ(report); err != nil {
			log.Warnf("Failed to publish report to RabbitMQ: %v", err)
			// Continue to return the response even if publish fails
		}
	}

	// Return JSON response (for backward compatibility)
	c.JSON(http.StatusOK, gin.H{
		"repo":     report.Repo,
		"branch":   report.Branch,
		"commit":   report.Commit,
		"coverage": report.Coverage.Raw,
	})
}

// getProfileFromGocServer gets profile data from the internal goc server
func (w *Wrapper) getProfileFromGocServer(param *cover.ProfileParam) ([]byte, error) {
	// Create a worker to call the goc server
	worker := cover.NewWorker(w.gocServerURL)
	return worker.Profile(*param)
}

// publishToRabbitMQ publishes the coverage report to RabbitMQ
func (w *Wrapper) publishToRabbitMQ(report CoverageReportMessage) error {
	if w.rabbitMQCh == nil {
		return fmt.Errorf("RabbitMQ channel is not initialized")
	}

	jsonData, err := json.Marshal(report)
	if err != nil {
		return fmt.Errorf("failed to marshal report: %v", err)
	}

	err = w.rabbitMQCh.Publish(
		"coverage_exchange",
		"coverage.report",
		false,
		false,
		amqp.Publishing{
			ContentType: "application/json",
			Body:        jsonData,
		},
	)
	if err != nil {
		return fmt.Errorf("failed to publish message: %v", err)
	}

	log.Infof("Successfully published coverage report to RabbitMQ: repo=%s, branch=%s, commit=%s",
		report.Repo, report.Branch, report.Commit)
	return nil
}

// Run starts the wrapper server
func (w *Wrapper) Run(port string) error {
	// Start goc server in the background on a random port
	listener, err := net.Listen("tcp", ":0")
	if err != nil {
		return fmt.Errorf("failed to create listener for goc server: %v", err)
	}

	gocPort := listener.Addr().(*net.TCPAddr).Port
	w.gocServerURL = fmt.Sprintf("http://127.0.0.1:%d", gocPort)

	log.Infof("Starting internal goc server on %s", w.gocServerURL)

	// Start goc server in a goroutine
	go func() {
		gocRouter := w.gocServer.Route(nil)
		if err := gocRouter.RunListener(listener); err != nil {
			log.Fatalf("Failed to start goc server: %v", err)
		}
	}()

	// Start wrapper server
	f, err := os.Create("goc-wrapper.log")
	if err != nil {
		log.Warnf("failed to create log file, err: %v", err)
		r := w.Route(os.Stdout)
		log.Infof("Starting wrapper server on %s", port)
		return r.Run(port)
	}
	defer f.Close()

	mw := io.MultiWriter(f, os.Stdout)
	r := w.Route(mw)
	log.Infof("Starting wrapper server on %s", port)
	return r.Run(port)
}
