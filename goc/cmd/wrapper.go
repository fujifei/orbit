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

package cmd

import (
	"log"

	"github.com/qiniu/goc/pkg/cover"
	"github.com/qiniu/goc/pkg/wrapper"
	"github.com/spf13/cobra"
)

var wrapperCmd = &cobra.Command{
	Use:   "wrapper",
	Short: "Start a wrapper server that wraps goc server with structured data reporting",
	Long: `Start a wrapper server that wraps goc server with structured data reporting.
The wrapper adds repo, branch, commit, and CI information to coverage data and publishes it to RabbitMQ.`,
	Example: `
# Start a wrapper server on default port :7777
goc wrapper

# Start a wrapper server on port :8080
goc wrapper --port=:8080

# Start a wrapper server with RabbitMQ URL
goc wrapper --rabbitmq-url=amqp://coverage:coverage123@localhost:5672/
`,
	Run: func(cmd *cobra.Command, args []string) {
		// Create goc server
		server, err := cover.NewFileBasedServer(wrapperLocalPersistence)
		if err != nil {
			log.Fatalf("New file based server failed, err: %v", err)
		}
		server.IPRevise = wrapperIPRevise

		// Create wrapper
		w, err := wrapper.NewWrapper(server, wrapperRabbitMQURL)
		if err != nil {
			log.Fatalf("New wrapper failed, err: %v", err)
		}
		defer w.Close()

		// Start wrapper server
		if err := w.Run(wrapperPort); err != nil {
			log.Fatalf("Failed to start wrapper server: %v", err)
		}
	},
}

var (
	wrapperPort              string
	wrapperLocalPersistence  string
	wrapperIPRevise          bool
	wrapperRabbitMQURL       string
)

func init() {
	wrapperCmd.Flags().StringVarP(&wrapperPort, "port", "", ":7777", "listen port to start the wrapper server")
	wrapperCmd.Flags().StringVarP(&wrapperLocalPersistence, "local-persistence", "", "_svrs_address.txt", "the file to save services address information for goc server")
	wrapperCmd.Flags().BoolVarP(&wrapperIPRevise, "ip_revise", "", true, "whether to do ip revise during registering. Recommend to set this as false if under NAT or Proxy environment")
	wrapperCmd.Flags().StringVarP(&wrapperRabbitMQURL, "rabbitmq-url", "", "", "RabbitMQ connection URL to publish coverage data (e.g., amqp://user:pass@host:port/)")
	rootCmd.AddCommand(wrapperCmd)
}

