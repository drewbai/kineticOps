"""GitOps commit/push integration for the control loop."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from action_engine.patch_generator import PatchArtifact


class GitOpsVerificationError(RuntimeError):
    """Raised when post-commit verification fails."""


@dataclass(frozen=True)
class GitOpsConfig:
    repo_url: str
    target_branch: str = "main"
    deployment_path: str = ""
    author_name: str = "kinetic-operator"
    author_email: str = "kinetic-operator@example.com"


@dataclass(frozen=True)
class GitOpsCommitResult:
    commit: str
    branch: str
    manifest_path: str
    repository: str
    verification: str


class GitOpsCommitter:
    """Clone, patch, and push GitOps changes with optional verification."""

    def __init__(self, *, git_bin: str | None = None) -> None:
        self.git_bin = git_bin or os.getenv("KINETICOPS_GIT_BIN", "git")
        self.local_repo = os.getenv("KINETICOPS_GITOPS_LOCAL_REPO", "").strip()
        self.github_token = os.getenv("KINETICOPS_GITHUB_TOKEN", "").strip()

    def commit(
        self,
        artifact: PatchArtifact,
        config: GitOpsConfig,
        metadata: dict[str, Any] | None = None,
    ) -> GitOpsCommitResult:
        if not artifact.content:
            raise ValueError("patch content is empty")
        repo_path, cleanup = self._prepare_repo(config)
        try:
            manifest_path = self._write_manifest(repo_path, config, artifact)
            commit_message = self._build_commit_message(artifact, metadata)
            self._ensure_identity(repo_path, config)
            self._git(["add", str(manifest_path)], cwd=repo_path)
            self._git(["commit", "-m", commit_message], cwd=repo_path)
            self._git(["push", "origin", config.target_branch], cwd=repo_path)
            verification_summary = self._verify_state(repo_path)
            commit_sha = self._git(["rev-parse", "HEAD"], cwd=repo_path).strip()
        finally:
            cleanup()

        return GitOpsCommitResult(
            commit=commit_sha,
            branch=config.target_branch,
            manifest_path=str(manifest_path),
            repository=config.repo_url,
            verification=verification_summary,
        )

    # Internal helpers -----------------------------------------------------------------

    def _prepare_repo(self, config: GitOpsConfig) -> tuple[Path, Any]:
        if self.local_repo:
            repo_dir = Path(self.local_repo).expanduser().resolve()
            if not (repo_dir / ".git").exists():
                raise FileNotFoundError(f"local GitOps repo not found: {repo_dir}")

            def _noop_cleanup() -> None:
                return None

            self._git(["checkout", config.target_branch], cwd=repo_dir)
            self._git(["pull", "origin", config.target_branch], cwd=repo_dir)
            return repo_dir, _noop_cleanup

        temp_dir = Path(tempfile.mkdtemp(prefix="kineticops-gitops-"))
        repo_url = self._hydrate_repo_url(config.repo_url)
        try:
            self._git(
                [
                    "clone",
                    "--branch",
                    config.target_branch,
                    "--single-branch",
                    repo_url,
                    str(temp_dir),
                ]
            )
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

        def _cleanup() -> None:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return temp_dir, _cleanup

    def _write_manifest(
        self, repo_path: Path, config: GitOpsConfig, artifact: PatchArtifact
    ) -> Path:
        deploy_dir = (repo_path / config.deployment_path).resolve()
        if not str(deploy_dir).startswith(str(repo_path)):
            raise ValueError("deployment_path must remain inside the repository root")
        deploy_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = deploy_dir / artifact.filename
        manifest_path.write_text(artifact.content, encoding="utf-8")
        return manifest_path.relative_to(repo_path)

    def _ensure_identity(self, repo_path: Path, config: GitOpsConfig) -> None:
        self._git(["config", "user.name", config.author_name], cwd=repo_path)
        self._git(["config", "user.email", config.author_email], cwd=repo_path)

    def _build_commit_message(
        self, artifact: PatchArtifact, metadata: dict[str, Any] | None
    ) -> str:
        loop_name = (metadata or {}).get("loop") or "kineticops-loop"
        reason = artifact.summary or "drift detected"
        return f"[KineticOps] {loop_name}: {reason}"

    def _verify_state(self, repo_path: Path) -> str:
        status = self._git(["status", "--short"], cwd=repo_path)
        if status.strip():
            raise GitOpsVerificationError("repository dirty after commit")
        return "workspace clean"

    def _hydrate_repo_url(self, repo_url: str) -> str:
        if not self.github_token:
            return repo_url
        prefix = "https://github.com/"
        if repo_url.startswith(prefix):
            return repo_url.replace(
                prefix, f"https://{self.github_token}:x-oauth-basic@github.com/", 1
            )
        return repo_url

    def _git(self, args: list[str], cwd: Path | None = None) -> str:
        completed = subprocess.run(  # noqa: S603,S607 - intentional git invocation
            [self.git_bin, *args],
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout
