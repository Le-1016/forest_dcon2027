package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"strings"

	"github.com/jackc/pgx/v5/pgxpool"
)

const openRouterURL = "https://openrouter.ai/api/v1/chat/completions"

const forestSystemPrompt = `あなたは森林保全システムFORESTのAIアシスタントです。
利用可能なツールを使って、データベースに保存された観測結果に基づいて日本語で回答してください。

重要:
- 観測データにない事実を推測で断定しないでください。
- confidenceはAIモデルの判定信頼度であり、森林や樹木の健康度そのものではありません。
- confidenceの上昇だけを根拠に「状態が改善した」と判断してはいけません。
- 比較するときは高度、カメラ角度など観測条件の違いも考慮してください。`

type AIChatRequest struct {
	Message string `json:"message"`
}

type AIChatResponse struct {
	Answer string `json:"answer"`
}

type toolCall struct {
	ID       string `json:"id"`
	Type     string `json:"type"`
	Function struct {
		Name      string `json:"name"`
		Arguments string `json:"arguments"`
	} `json:"function"`
}

type openRouterMessage struct {
	Role       string     `json:"role"`
	Content    any        `json:"content,omitempty"`
	ToolCalls  []toolCall `json:"tool_calls,omitempty"`
	ToolCallID string     `json:"tool_call_id,omitempty"`
}

type openRouterResponse struct {
	Choices []struct {
		Message openRouterMessage `json:"message"`
	} `json:"choices"`
	Error *struct {
		Message string `json:"message"`
	} `json:"error,omitempty"`
}

type observationHistoryArgs struct {
	AreaID string `json:"area_id"`
	SiteID string `json:"site_id"`
}

func callOpenRouter(ctx context.Context, payload any) (openRouterResponse, error) {
	key := strings.TrimSpace(os.Getenv("OPENROUTER_API_KEY"))
	if key == "" {
		return openRouterResponse{}, fmt.Errorf("OPENROUTER_API_KEY is not configured")
	}

	body, err := json.Marshal(payload)
	if err != nil {
		return openRouterResponse{}, err
	}

	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		openRouterURL,
		bytes.NewReader(body),
	)
	if err != nil {
		return openRouterResponse{}, err
	}

	req.Header.Set("Authorization", "Bearer "+key)
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return openRouterResponse{}, err
	}
	defer resp.Body.Close()

	var result openRouterResponse
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return result, err
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		if result.Error != nil {
			return result, fmt.Errorf("OpenRouter: %s", result.Error.Message)
		}
		return result, fmt.Errorf("OpenRouter HTTP %d", resp.StatusCode)
	}

	if len(result.Choices) == 0 {
		return result, fmt.Errorf("OpenRouter returned no choices")
	}

	return result, nil
}

func observationHistoryTool() map[string]any {
	return map[string]any{
		"type": "function",
		"function": map[string]any{
			"name":        "get_observation_history",
			"description": "指定された森林エリアと観測地点の観測履歴を取得する",
			"parameters": map[string]any{
				"type": "object",
				"properties": map[string]any{
					"area_id": map[string]any{
						"type":        "string",
						"description": "森林エリアID。例: A-17",
					},
					"site_id": map[string]any{
						"type":        "string",
						"description": "観測地点ID。例: S-17-01",
					},
				},
				"required":             []string{"area_id", "site_id"},
				"additionalProperties": false,
			},
		},
	}
}

func executeToolCall(
	ctx context.Context,
	pool *pgxpool.Pool,
	call toolCall,
) (string, error) {
	switch call.Function.Name {
	case "get_observation_history":
		var args observationHistoryArgs
		if err := json.Unmarshal([]byte(call.Function.Arguments), &args); err != nil {
			return "", fmt.Errorf("invalid tool arguments: %w", err)
		}

		args.AreaID = strings.TrimSpace(args.AreaID)
		args.SiteID = strings.TrimSpace(args.SiteID)

		if args.AreaID == "" || args.SiteID == "" {
			return "", fmt.Errorf("area_id and site_id are required")
		}

		history, err := getObservationHistory(
			ctx,
			pool,
			args.AreaID,
			args.SiteID,
		)
		if err != nil {
			return "", err
		}

		result, err := json.Marshal(history)
		if err != nil {
			return "", err
		}

		return string(result), nil

	default:
		return "", fmt.Errorf("tool is not allowed: %s", call.Function.Name)
	}
}

func handleAIChat(pool *pgxpool.Pool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			w.Header().Set("Allow", "POST")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}

		var req AIChatRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, "invalid JSON", http.StatusBadRequest)
			return
		}

		req.Message = strings.TrimSpace(req.Message)
		if req.Message == "" {
			http.Error(w, "message is required", http.StatusBadRequest)
			return
		}

		messages := []openRouterMessage{
			{
				Role:    "system",
				Content: forestSystemPrompt,
			},
			{
				Role:    "user",
				Content: req.Message,
			},
		}

		firstPayload := map[string]any{
			"model":       "openrouter/free",
			"messages":    messages,
			"tools":       []any{observationHistoryTool()},
			"tool_choice": "auto",
		}

		first, err := callOpenRouter(r.Context(), firstPayload)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadGateway)
			return
		}

		assistantMessage := first.Choices[0].Message

		if len(assistantMessage.ToolCalls) == 0 {
			answer, ok := assistantMessage.Content.(string)
			if !ok || strings.TrimSpace(answer) == "" {
				http.Error(w, "LLM returned no answer or tool call", http.StatusBadGateway)
				return
			}

			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(AIChatResponse{
				Answer: answer,
			})
			return
		}

		if len(assistantMessage.ToolCalls) != 1 {
			http.Error(w, "only one tool call is allowed", http.StatusBadGateway)
			return
		}

		call := assistantMessage.ToolCalls[0]

		toolResult, err := executeToolCall(
			r.Context(),
			pool,
			call,
		)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadGateway)
			return
		}

		messages = append(messages, assistantMessage)
		messages = append(messages, openRouterMessage{
			Role:       "tool",
			Content:    toolResult,
			ToolCallID: call.ID,
		})

		secondPayload := map[string]any{
			"model":    "openrouter/free",
			"messages": messages,
		}

		second, err := callOpenRouter(r.Context(), secondPayload)
		if err != nil {
			http.Error(w, err.Error(), http.StatusBadGateway)
			return
		}

		answer, ok := second.Choices[0].Message.Content.(string)
		if !ok || strings.TrimSpace(answer) == "" {
			http.Error(w, "LLM returned an empty final answer", http.StatusBadGateway)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(AIChatResponse{
			Answer: answer,
		})
	}
}
