// Package v1alpha1 defines the KineticOpsLoop API schema.
package v1alpha1

import (
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"sigs.k8s.io/controller-runtime/pkg/scheme"
)

var (
	// GroupVersion is used to register these objects with the scheme.
	GroupVersion = schema.GroupVersion{Group: "ops.kineticops.dev", Version: "v1alpha1"}
	// SchemeBuilder collects the go types to add to the runtime Scheme.
	SchemeBuilder = &scheme.Builder{GroupVersion: GroupVersion}
	// AddToScheme applies this group's types to a Scheme.
	AddToScheme = SchemeBuilder.AddToScheme
)

// CadenceSpec captures how often the controller evaluates drift.
type CadenceSpec struct {
	CheckIntervalSeconds int32  `json:"checkIntervalSeconds"`
	JitterPercentage     *int32 `json:"jitterPercentage,omitempty"`
}

// LabelSelector mirrors corev1 label selector but keeps this file lightweight.
type LabelSelector struct {
	MatchLabels      map[string]string          `json:"matchLabels,omitempty"`
	MatchExpressions []LabelSelectorRequirement `json:"matchExpressions,omitempty"`
}

// LabelSelectorRequirement models one selector clause.
type LabelSelectorRequirement struct {
	Key      string   `json:"key"`
	Operator string   `json:"operator"`
	Values   []string `json:"values,omitempty"`
}

// TargetSpec scopes which clusters/namespaces the loop manages.
type TargetSpec struct {
	NamespaceSelector *LabelSelector    `json:"namespaceSelector,omitempty"`
	ClusterRef        *ClusterReference `json:"clusterRef,omitempty"`
}

// ClusterReference points to credentials for an out-of-cluster target.
type ClusterReference struct {
	KubeconfigSecretRef SecretKeyReference `json:"kubeconfigSecretRef"`
}

// SecretKeyReference represents a namespaced secret key selector.
type SecretKeyReference struct {
	Name string `json:"name"`
	Key  string `json:"key,omitempty"`
}

// TelemetrySource configures a drift signal source.
type TelemetrySource struct {
	Name            string         `json:"name,omitempty"`
	Type            string         `json:"type"`
	IntervalSeconds *int32         `json:"intervalSeconds,omitempty"`
	Endpoint        string         `json:"endpoint,omitempty"`
	Selector        *LabelSelector `json:"selector,omitempty"`
}

// TelemetrySpec aggregates configured sources.
type TelemetrySpec struct {
	Sources []TelemetrySource `json:"sources,omitempty"`
}

// DriftPolicy defines desired state checks.
type DriftPolicy struct {
	Name             string           `json:"name"`
	Resource         DriftResourceRef `json:"resource"`
	Checks           []DriftCheck     `json:"checks,omitempty"`
	RemediationHints []string         `json:"remediationHints,omitempty"`
}

// DriftResourceRef identifies the component to inspect.
type DriftResourceRef struct {
	APIVersion string         `json:"apiVersion"`
	Kind       string         `json:"kind"`
	Namespace  string         `json:"namespace,omitempty"`
	Selector   *LabelSelector `json:"selector,omitempty"`
}

// DriftCheck is a simple field comparison rule.
type DriftCheck struct {
	FieldPath     string   `json:"fieldPath,omitempty"`
	ExpectedValue string   `json:"expectedValue,omitempty"`
	Tolerance     *float64 `json:"tolerance,omitempty"`
	Comparison    string   `json:"comparison,omitempty"`
}

// RemediationSpec contains the strategy for applying fixes.
type RemediationSpec struct {
	Strategy      string         `json:"strategy"`
	DryRun        *bool          `json:"dryRun,omitempty"`
	GitOps        *GitOpsSpec    `json:"gitOps,omitempty"`
	RolloutPolicy *RolloutPolicy `json:"rolloutPolicy,omitempty"`
}

// GitOpsSpec configures the GitOps integration path.
type GitOpsSpec struct {
	RepoURL              string              `json:"repoURL,omitempty"`
	TargetBranch         string              `json:"targetBranch,omitempty"`
	DeploymentPath       string              `json:"deploymentPath,omitempty"`
	Author               string              `json:"author,omitempty"`
	CredentialsSecretRef *SecretKeyReference `json:"credentialsSecretRef,omitempty"`
}

// RolloutPolicy configures guardrails while applying remediations.
type RolloutPolicy struct {
	MaxParallelRemediations *int32   `json:"maxParallelRemediations,omitempty"`
	PauseSeconds            *int32   `json:"pauseSeconds,omitempty"`
	VerificationGates       []string `json:"verificationGates,omitempty"`
}

// VerificationProbe describes a post-remediation probe.
type VerificationProbe struct {
	Name             string            `json:"name"`
	Type             string            `json:"type"`
	TimeoutSeconds   *int32            `json:"timeoutSeconds,omitempty"`
	SuccessThreshold *int32            `json:"successThreshold,omitempty"`
	FailureThreshold *int32            `json:"failureThreshold,omitempty"`
	Config           map[string]string `json:"config,omitempty"`
}

// VerificationSpec tells the controller how to validate fixes.
type VerificationSpec struct {
	Probes []VerificationProbe `json:"probes,omitempty"`
}

// AIPlannerSpec controls AI-assisted intent generation.
type AIPlannerSpec struct {
	Mode                 string              `json:"mode,omitempty"`
	Endpoint             string              `json:"endpoint,omitempty"`
	Model                string              `json:"model,omitempty"`
	TimeoutSeconds       *int32              `json:"timeoutSeconds,omitempty"`
	CredentialsSecretRef *SecretKeyReference `json:"credentialsSecretRef,omitempty"`
}

// KineticOpsLoopSpec defines desired state for the control loop.
type KineticOpsLoopSpec struct {
	Cadence       CadenceSpec       `json:"cadence"`
	Target        *TargetSpec       `json:"target,omitempty"`
	Telemetry     *TelemetrySpec    `json:"telemetry,omitempty"`
	DriftPolicies []DriftPolicy     `json:"driftPolicies,omitempty"`
	Remediation   RemediationSpec   `json:"remediation"`
	Verification  *VerificationSpec `json:"verification,omitempty"`
	AIPlanner     *AIPlannerSpec    `json:"aiPlanner,omitempty"`
}

// Condition describes controller-reported state.
type Condition struct {
	Type               string                 `json:"type"`
	Status             metav1.ConditionStatus `json:"status"`
	LastTransitionTime metav1.Time            `json:"lastTransitionTime"`
	Reason             string                 `json:"reason,omitempty"`
	Message            string                 `json:"message,omitempty"`
}

// LastRemediationStatus captures the final remediation attempt summary.
type LastRemediationStatus struct {
	StartedAt       *metav1.Time `json:"startedAt,omitempty"`
	CompletedAt     *metav1.Time `json:"completedAt,omitempty"`
	DriftSummary    string       `json:"driftSummary,omitempty"`
	AppliedStrategy string       `json:"appliedStrategy,omitempty"`
	GitOpsCommit    string       `json:"gitOpsCommit,omitempty"`
	VerifierSummary string       `json:"verifierSummary,omitempty"`
}

// KineticOpsLoopStatus represents the observed state.
type KineticOpsLoopStatus struct {
	Phase              string                 `json:"phase,omitempty"`
	ObservedGeneration int64                  `json:"observedGeneration,omitempty"`
	Conditions         []Condition            `json:"conditions,omitempty"`
	LastCheckTime      *metav1.Time           `json:"lastCheckTime,omitempty"`
	LastRemediation    *LastRemediationStatus `json:"lastRemediation,omitempty"`
}

// +kubebuilder:object:root=true
// +kubebuilder:subresource:status

// KineticOpsLoop is the Schema for the kineticopsloops API.
type KineticOpsLoop struct {
	metav1.TypeMeta   `json:",inline"`
	metav1.ObjectMeta `json:"metadata,omitempty"`

	Spec   KineticOpsLoopSpec   `json:"spec,omitempty"`
	Status KineticOpsLoopStatus `json:"status,omitempty"`
}

// +kubebuilder:object:root=true

// KineticOpsLoopList contains a list of KineticOpsLoop.
type KineticOpsLoopList struct {
	metav1.TypeMeta `json:",inline"`
	metav1.ListMeta `json:"metadata,omitempty"`
	Items           []KineticOpsLoop `json:"items"`
}

func init() {
	SchemeBuilder.Register(&KineticOpsLoop{}, &KineticOpsLoopList{})
}
