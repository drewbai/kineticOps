package controllers

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "strings"
    "time"

    opsv1alpha1 "github.com/drewbai/kineticOps/operator/api/v1alpha1"
    metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
)

// HTTPOrchestrator bridges the controller to the Python HTTP gateway.
type HTTPOrchestrator struct {
    endpoint string
    client   *http.Client
}

// NewHTTPOrchestrator constructs an HTTP orchestrator with sane defaults.
func NewHTTPOrchestrator(endpoint string, client *http.Client) *HTTPOrchestrator {
    base := strings.TrimRight(endpoint, "/")
    if client == nil {
        client = &http.Client{Timeout: 15 * time.Second}
    }
    return &HTTPOrchestrator{endpoint: base, client: client}
}

// orchestratorRequest is serialized and sent to the Python service.
type orchestratorRequest struct {
    Loop  orchestratorLoopPayload `json:"loop"`
    Event map[string]any          `json:"event,omitempty"`
}

type orchestratorLoopPayload struct {
    Metadata orchestratorLoopMetadata      `json:"metadata"`
    Spec     opsv1alpha1.KineticOpsLoopSpec `json:"spec"`
}

type orchestratorLoopMetadata struct {
    Name        string            `json:"name"`
    Namespace   string            `json:"namespace"`
    UID         string            `json:"uid,omitempty"`
    Labels      map[string]string `json:"labels,omitempty"`
    Annotations map[string]string `json:"annotations,omitempty"`
}

type orchestratorResponse struct {
    DriftDetected   bool                        `json:"driftDetected"`
    DriftSummary    string                      `json:"driftSummary"`
    Message         string                      `json:"message"`
    Phase           string                      `json:"phase"`
    LastRemediation *orchestratorRemediationDTO `json:"lastRemediation"`
}

type orchestratorRemediationDTO struct {
    StartedAt       string `json:"startedAt"`
    CompletedAt     string `json:"completedAt"`
    DriftSummary    string `json:"driftSummary"`
    AppliedStrategy string `json:"appliedStrategy"`
    GitOpsCommit    string `json:"gitOpsCommit"`
    VerifierSummary string `json:"verifierSummary"`
}

// Execute calls the Python service and translates the response into LoopExecutionResult.
func (h *HTTPOrchestrator) Execute(ctx context.Context, loop *opsv1alpha1.KineticOpsLoop) (LoopExecutionResult, error) {
    payload := orchestratorRequest{
        Loop: orchestratorLoopPayload{
            Metadata: orchestratorLoopMetadata{
                Name:        loop.Name,
                Namespace:   loop.Namespace,
                UID:         string(loop.UID),
                Labels:      loop.Labels,
                Annotations: loop.Annotations,
            },
            Spec: loop.Spec,
        },
        Event: map[string]any{
            "source":    "kineticops-controller",
            "loopName":  loop.Name,
            "namespace": loop.Namespace,
            "timestamp": time.Now().UTC().Format(time.RFC3339Nano),
        },
    }

    body, err := json.Marshal(payload)
    if err != nil {
        return LoopExecutionResult{}, fmt.Errorf("marshal orchestrator payload: %w", err)
    }

    url := h.endpoint + "/execute"
    req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(body))
    if err != nil {
        return LoopExecutionResult{}, fmt.Errorf("create orchestrator request: %w", err)
    }
    req.Header.Set("Content-Type", "application/json")

    resp, err := h.client.Do(req)
    if err != nil {
        return LoopExecutionResult{}, fmt.Errorf("call orchestrator: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode >= 400 {
        var errBody map[string]any
        _ = json.NewDecoder(resp.Body).Decode(&errBody)
        return LoopExecutionResult{}, fmt.Errorf("orchestrator returned %d: %v", resp.StatusCode, errBody)
    }

    var payloadResp orchestratorResponse
    if err := json.NewDecoder(resp.Body).Decode(&payloadResp); err != nil {
        return LoopExecutionResult{}, fmt.Errorf("decode orchestrator response: %w", err)
    }

    result := LoopExecutionResult{
        DriftDetected: payloadResp.DriftDetected,
        DriftSummary:  payloadResp.DriftSummary,
        Message:       payloadResp.Message,
        Phase:         payloadResp.Phase,
    }
    if payloadResp.LastRemediation != nil {
        result.LastRemediation = convertRemediationDTO(payloadResp.LastRemediation)
    }
    return result, nil
}

func convertRemediationDTO(dto *orchestratorRemediationDTO) *opsv1alpha1.LastRemediationStatus {
    lr := &opsv1alpha1.LastRemediationStatus{
        DriftSummary:    dto.DriftSummary,
        AppliedStrategy: dto.AppliedStrategy,
        GitOpsCommit:    dto.GitOpsCommit,
        VerifierSummary: dto.VerifierSummary,
    }
    if t := parseRFC3339(dto.StartedAt); t != nil {
        lr.StartedAt = t
    }
    if t := parseRFC3339(dto.CompletedAt); t != nil {
        lr.CompletedAt = t
    }
    return lr
}

func parseRFC3339(value string) *metav1.Time {
    if value == "" {
        return nil
    }
    ts, err := time.Parse(time.RFC3339Nano, value)
    if err != nil {
        return nil
    }
    mt := metav1.NewTime(ts)
    return &mt
}
