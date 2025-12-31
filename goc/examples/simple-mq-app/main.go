package main

import (
	"fmt"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "Hello, World!")
	})

	http.HandleFunc("/add", func(w http.ResponseWriter, r *http.Request) {
		result := add(10, 20)
		fmt.Fprintf(w, "Result: %d", result)
	})

	http.HandleFunc("/multiply", func(w http.ResponseWriter, r *http.Request) {
		result := multiply(5, 6)
		fmt.Fprintf(w, "Result: %d", result)
	})

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	fmt.Printf("Server starting on port %s\n", port)
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		fmt.Printf("Server failed: %v\n", err)
		os.Exit(1)
	}
}

func add(a, b int) int {
	return a + b
}

func multiply(a, b int) int {
	return a * b
}

