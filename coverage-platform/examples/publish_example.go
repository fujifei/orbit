package main

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"github.com/streadway/amqp"
)

// CoverageReportMessage 覆盖率报告消息结构
type CoverageReportMessage struct {
	Repo      string       `json:"repo"`
	RepoID    string       `json:"repo_id"`
	Branch    string       `json:"branch"`
	Commit    string       `json:"commit"`
	CI        CIMetadata   `json:"ci"`
	Coverage  CoverageData `json:"coverage"`
	Timestamp int64        `json:"timestamp"`
}

// CIMetadata CI元数据
type CIMetadata struct {
	Provider   string `json:"provider"`
	PipelineID string `json:"pipeline_id"`
	JobID      string `json:"job_id"`
}

// CoverageData 覆盖率数据
type CoverageData struct {
	Format string `json:"format"`
	Raw    string `json:"raw"`
}

func main() {
	// 连接RabbitMQ
	conn, err := amqp.Dial("amqp://coverage:coverage123@localhost:5672/")
	if err != nil {
		log.Fatalf("Failed to connect to RabbitMQ: %v", err)
	}
	defer conn.Close()

	ch, err := conn.Channel()
	if err != nil {
		log.Fatalf("Failed to open channel: %v", err)
	}
	defer ch.Close()

	// 声明交换机（如果不存在）
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
		log.Fatalf("Failed to declare exchange: %v", err)
	}

	// 创建示例覆盖率报告
	repo := "github.com/xxx/tuna"
	// 生成 repo_id: 使用 SHA256 hash
	hash := sha256.Sum256([]byte(repo))
	repoID := hex.EncodeToString(hash[:])

	report := CoverageReportMessage{
		Repo:   repo,
		RepoID: repoID,
		Branch: "main",
		Commit: "a1b2c3d4e5f6",
		CI: CIMetadata{
			Provider:   "gitlab",
			PipelineID: "12345",
			JobID:      "67890",
		},
		Coverage: CoverageData{
			Format: "goc",
			Raw: `mode: set
github.com/xxx/tuna/file1.go:10.2,20.3 1
github.com/xxx/tuna/file1.go:30.4,40.5 0
github.com/xxx/tuna/file2.go:5.1,15.2 3
github.com/xxx/tuna/file2.go:20.1,25.3 2`,
		},
		Timestamp: time.Now().Unix(),
	}

	// 序列化为JSON
	body, err := json.Marshal(report)
	if err != nil {
		log.Fatalf("Failed to marshal report: %v", err)
	}

	// 发布消息（设置持久化）
	err = ch.Publish(
		"coverage_exchange",
		"coverage.report",
		false,
		false,
		amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent, // 消息持久化
			Body:         body,
		},
	)
	if err != nil {
		log.Fatalf("Failed to publish message: %v", err)
	}

	fmt.Println("Coverage report published successfully!")
	fmt.Printf("Repo: %s\n", report.Repo)
	fmt.Printf("RepoID: %s\n", report.RepoID)
	fmt.Printf("Branch: %s\n", report.Branch)
	fmt.Printf("Commit: %s\n", report.Commit)
}

