package controllers

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"time"

	opsv1alpha1 "github.com/drewbai/kineticOps/operator/api/v1alpha1"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/apimachinery/pkg/types"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"
	"sigs.k8s.io/controller-runtime/pkg/controller/controllerutil"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

const (
	kineticOpsFinalizer = "ops.kineticops.dev/finalizer"

	conditionReady = "LoopReady"
	conditionDrift = "DriftDetected"

	phasePending     = "Pending"
	phaseReconciling = "Reconciling"
	phaseHealthy     = "Healthy"
	phaseDrifted     = "Drifted"
	phaseError       = "Error"
)

// LoopExecutionResult captures the output of orchestrating one control-loop iteration.
type LoopExecutionResult struct {
	DriftDetected   bool
	DriftSummary    string
	Message         string
	Phase           string
	LastRemediation *opsv1alpha1.LastRemediationStatus
}

// LoopOrchestrator abstracts the Python-based automation pipeline so the controller
// can remain in Go while delegating drift detection + remediation to the existing stubs.
type LoopOrchestrator interface {
	Execute(ctx context.Context, loop *opsv1alpha1.KineticOpsLoop) (LoopExecutionResult, error)
}

// NoopOrchestrator is a placeholder until the Python runtime is wired in via gRPC/HTTP.
type NoopOrchestrator struct{}

// Execute implements LoopOrchestrator without performing real work.
func (NoopOrchestrator) Execute(ctx context.Context, loop *opsv1alpha1.KineticOpsLoop) (LoopExecutionResult, error) {
	_ = ctx
	return LoopExecutionResult{Phase: phasePending, Message: "no orchestrator wired"}, nil
}

// KineticOpsLoopReconciler reconciles KineticOpsLoop resources.
type KineticOpsLoopReconciler struct {
	client.Client
	Scheme       *runtime.Scheme
	Orchestrator LoopOrchestrator
}

//+kubebuilder:rbac:groups=ops.kineticops.dev,resources=kineticopsloops,verbs=get;list;watch;create;update;patch;delete
//+kubebuilder:rbac:groups=ops.kineticops.dev,resources=kineticopsloops/status,verbs=get;update;patch
//+kubebuilder:rbac:groups=ops.kineticops.dev,resources=kineticopsloops/finalizers,verbs=update
//+kubebuilder:rbac:groups="",resources=secrets;configmaps,verbs=get;list;watch

// Reconcile drives the declarative control loop for each KineticOpsLoop instance.
func (r *KineticOpsLoopReconciler) Reconcile(ctx context.Context, req ctrl.Request) (ctrl.Result, error) {
	logger := log.FromContext(ctx).WithValues("kineticopsloop", req.NamespacedName)

	var loop opsv1alpha1.KineticOpsLoop
	if err := r.Get(ctx, req.NamespacedName, &loop); err != nil {
		if apierrors.IsNotFound(err) {
			return ctrl.Result{}, nil
		}
		return ctrl.Result{}, err
	}

	if loop.ObjectMeta.DeletionTimestamp.IsZero() {
		if err := r.ensureFinalizer(ctx, &loop); err != nil {
			return ctrl.Result{}, err
		}
	} else {
		if controllerutil.ContainsFinalizer(&loop, kineticOpsFinalizer) {
			// TODO: ensure any out-of-band jobs are terminated.
			controllerutil.RemoveFinalizer(&loop, kineticOpsFinalizer)
			if err := r.Update(ctx, &loop); err != nil {
				return ctrl.Result{}, err
			}
		}
		return ctrl.Result{}, nil
	}

	if err := r.validateSpec(&loop); err != nil {
		logger.Error(err, "spec validation failed")
		if errStatus := r.patchStatus(ctx, &loop, func(status *opsv1alpha1.KineticOpsLoopStatus) {
			status.Phase = phaseError
			r.setCondition(status, conditionReady, metav1.ConditionFalse, "SpecInvalid", err.Error())
		}); errStatus != nil {
			return ctrl.Result{}, errStatus
		}
		// Requeue so the user gets another status update if they change the spec.
		return ctrl.Result{RequeueAfter: time.Minute}, nil
	}

	requeueAfter := time.Duration(loop.Spec.Cadence.CheckIntervalSeconds) * time.Second
	statusPatch := func(status *opsv1alpha1.KineticOpsLoopStatus) {
		status.ObservedGeneration = loop.Generation
		now := metav1.NewTime(time.Now().UTC())
		status.LastCheckTime = &now
		status.Phase = phaseReconciling
		r.setCondition(status, conditionReady, metav1.ConditionTrue, "SpecValid", "reconcile in progress")
	}
	if err := r.patchStatus(ctx, &loop, statusPatch); err != nil {
		return ctrl.Result{}, err
	}

	var execResult LoopExecutionResult
	var execErr error
	if r.Orchestrator != nil {
		execResult, execErr = r.Orchestrator.Execute(ctx, &loop)
	} else {
		execResult = LoopExecutionResult{Phase: phasePending, Message: "orchestrator nil"}
	}

	if execErr != nil {
		logger.Error(execErr, "orchestration failed")
		if err := r.patchStatus(ctx, &loop, func(status *opsv1alpha1.KineticOpsLoopStatus) {
			status.Phase = phaseError
			r.setCondition(status, conditionReady, metav1.ConditionFalse, "ExecutionError", execErr.Error())
		}); err != nil {
			return ctrl.Result{}, err
		}
		return ctrl.Result{RequeueAfter: requeueAfter}, execErr
	}

	if execResult.Phase == "" {
		execResult.Phase = phaseHealthy
	}

	if err := r.patchStatus(ctx, &loop, func(status *opsv1alpha1.KineticOpsLoopStatus) {
		status.Phase = execResult.Phase
		if execResult.DriftDetected {
			r.setCondition(status, conditionDrift, metav1.ConditionTrue, "DriftObserved", execResult.DriftSummary)
		} else {
			r.setCondition(status, conditionDrift, metav1.ConditionFalse, "NoDrift", execResult.Message)
		}
		if execResult.LastRemediation != nil {
			status.LastRemediation = execResult.LastRemediation
		}
	}); err != nil {
		return ctrl.Result{}, err
	}

	return ctrl.Result{RequeueAfter: requeueAfter}, nil
}

func (r *KineticOpsLoopReconciler) ensureFinalizer(ctx context.Context, loop *opsv1alpha1.KineticOpsLoop) error {
	if controllerutil.ContainsFinalizer(loop, kineticOpsFinalizer) {
		return nil
	}
	controllerutil.AddFinalizer(loop, kineticOpsFinalizer)
	return r.Update(ctx, loop)
}

func (r *KineticOpsLoopReconciler) validateSpec(loop *opsv1alpha1.KineticOpsLoop) error {
	if loop.Spec.Cadence.CheckIntervalSeconds < 10 {
		return fmt.Errorf("cadence.checkIntervalSeconds must be >= 10s")
	}
	strategy := loop.Spec.Remediation.Strategy
	if strategy == "" {
		return errors.New("remediation.strategy is required")
	}
	if strategy == "GitOps" {
		if loop.Spec.Remediation.GitOps == nil || loop.Spec.Remediation.GitOps.RepoURL == "" {
			return errors.New("gitOps.repoURL is required when strategy is GitOps")
		}
	}
	return nil
}

func (r *KineticOpsLoopReconciler) patchStatus(ctx context.Context, loop *opsv1alpha1.KineticOpsLoop, mutate func(status *opsv1alpha1.KineticOpsLoopStatus)) error {
	original := loop.DeepCopy()
	mutate(&loop.Status)
	return r.Status().Patch(ctx, loop, client.MergeFrom(original))
}

func (r *KineticOpsLoopReconciler) setCondition(status *opsv1alpha1.KineticOpsLoopStatus, condType string, condStatus metav1.ConditionStatus, reason, message string) {
	normalized := condStatus
	if condStatus == metav1.ConditionTrue || condStatus == metav1.ConditionFalse {
		normalized = metav1.ConditionStatus(strings.ToLower(string(condStatus)))
	}
	now := metav1.NewTime(time.Now().UTC())
	for idx := range status.Conditions {
		cond := &status.Conditions[idx]
		if cond.Type == condType {
			if cond.Status != normalized {
				cond.LastTransitionTime = now
			}
			cond.Status = normalized
			cond.Reason = reason
			cond.Message = message
			return
		}
	}
	status.Conditions = append(status.Conditions, opsv1alpha1.Condition{
		Type:               condType,
		Status:             normalized,
		Reason:             reason,
		Message:            message,
		LastTransitionTime: now,
	})
}

// SetupWithManager wires the controller into the manager.
func (r *KineticOpsLoopReconciler) SetupWithManager(mgr ctrl.Manager) error {
	return ctrl.NewControllerManagedBy(mgr).
		For(&opsv1alpha1.KineticOpsLoop{}).
		Complete(r)
}

// FetchLoop is a helper for tests to retrieve Loop objects without referencing the client directly.
func (r *KineticOpsLoopReconciler) FetchLoop(ctx context.Context, namespace, name string) (*opsv1alpha1.KineticOpsLoop, error) {
	var loop opsv1alpha1.KineticOpsLoop
	if err := r.Get(ctx, types.NamespacedName{Namespace: namespace, Name: name}, &loop); err != nil {
		return nil, err
	}
	return &loop, nil
}
