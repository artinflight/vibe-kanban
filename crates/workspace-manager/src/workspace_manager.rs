use std::path::{Path, PathBuf};

use db::{
    DBService,
    models::{
        file::WorkspaceAttachment,
        repo::{Repo, RepoError},
        requests::WorkspaceRepoInput,
        session::Session,
        workspace::Workspace as DbWorkspace,
        workspace_repo::{CreateWorkspaceRepo, RepoWithTargetBranch, WorkspaceRepo},
    },
};
use git::{GitService, GitServiceError};
use thiserror::Error;
use tracing::{debug, error, info, warn};
use uuid::Uuid;
use worktree_manager::{WorktreeCleanup, WorktreeError, WorktreeManager};

#[derive(Debug, Clone)]
pub struct RepoWorkspaceInput {
    pub repo: Repo,
    pub target_branch: String,
}

impl RepoWorkspaceInput {
    pub fn new(repo: Repo, target_branch: String) -> Self {
        Self {
            repo,
            target_branch,
        }
    }
}

#[derive(Debug, Error)]
pub enum WorkspaceError {
    #[error(transparent)]
    Database(#[from] sqlx::Error),
    #[error(transparent)]
    Repo(#[from] RepoError),
    #[error(transparent)]
    Worktree(#[from] WorktreeError),
    #[error(transparent)]
    GitService(#[from] GitServiceError),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Workspace not found")]
    WorkspaceNotFound,
    #[error("Repository already attached to workspace")]
    RepoAlreadyAttached,
    #[error("Branch '{branch}' does not exist in repository '{repo_name}'")]
    BranchNotFound { repo_name: String, branch: String },
    #[error("No repositories provided")]
    NoRepositories,
    #[error("Partial workspace creation failed: {0}")]
    PartialCreation(String),
}

/// Info about a single repo's worktree within a workspace
#[derive(Debug, Clone)]
pub struct RepoWorktree {
    pub repo_id: Uuid,
    pub repo_name: String,
    pub source_repo_path: PathBuf,
    pub worktree_path: PathBuf,
}

/// A container directory holding worktrees for all project repos
#[derive(Debug, Clone)]
pub struct WorktreeContainer {
    pub workspace_dir: PathBuf,
    pub worktrees: Vec<RepoWorktree>,
}

#[derive(Debug, Clone)]
pub struct WorkspaceDeletionContext {
    pub workspace_id: Uuid,
    pub branch_name: String,
    pub workspace_dir: Option<PathBuf>,
    pub repositories: Vec<Repo>,
    pub repo_paths: Vec<PathBuf>,
    pub session_ids: Vec<Uuid>,
}

#[derive(Clone)]
pub struct ManagedWorkspace {
    pub workspace: DbWorkspace,
    pub repos: Vec<RepoWithTargetBranch>,
    db: DBService,
}

impl ManagedWorkspace {
    fn new(db: DBService, workspace: DbWorkspace, repos: Vec<RepoWithTargetBranch>) -> Self {
        Self {
            workspace,
            repos,
            db,
        }
    }

    async fn attach_repository(&self, repo: &WorkspaceRepoInput) -> Result<(), sqlx::Error> {
        let create_repo = CreateWorkspaceRepo {
            repo_id: repo.repo_id,
            target_branch: repo.target_branch.clone(),
        };

        WorkspaceRepo::create_many(
            &self.db.pool,
            self.workspace.id,
            std::slice::from_ref(&create_repo),
        )
        .await
        .map(|_| ())
    }

    async fn refresh(&mut self) -> Result<(), WorkspaceError> {
        self.workspace = DbWorkspace::find_by_id(&self.db.pool, self.workspace.id)
            .await?
            .ok_or(WorkspaceError::WorkspaceNotFound)?;
        self.repos = WorkspaceRepo::find_repos_with_target_branch_for_workspace(
            &self.db.pool,
            self.workspace.id,
        )
        .await?;
        Ok(())
    }

    pub async fn add_repository(
        &mut self,
        repo_ref: &WorkspaceRepoInput,
        git: &GitService,
    ) -> Result<(), WorkspaceError> {
        let repo = Repo::find_by_id(&self.db.pool, repo_ref.repo_id)
            .await?
            .ok_or(RepoError::NotFound)?;

        if !git.check_branch_exists(&repo.path, &repo_ref.target_branch)? {
            return Err(WorkspaceError::BranchNotFound {
                repo_name: repo.name,
                branch: repo_ref.target_branch.clone(),
            });
        }

        if WorkspaceRepo::find_by_workspace_and_repo_id(
            &self.db.pool,
            self.workspace.id,
            repo_ref.repo_id,
        )
        .await?
        .is_some()
        {
            return Err(WorkspaceError::RepoAlreadyAttached);
        }

        self.attach_repository(repo_ref).await?;
        self.refresh().await?;
        Ok(())
    }

    pub async fn associate_attachments(&self, attachment_ids: &[Uuid]) -> Result<(), sqlx::Error> {
        if attachment_ids.is_empty() {
            return Ok(());
        }

        WorkspaceAttachment::associate_many_dedup(&self.db.pool, self.workspace.id, attachment_ids)
            .await
    }

    pub async fn prepare_deletion_context(&self) -> Result<WorkspaceDeletionContext, sqlx::Error> {
        let repositories =
            WorkspaceRepo::find_repos_for_workspace(&self.db.pool, self.workspace.id).await?;
        let session_ids = Session::find_by_workspace_id(&self.db.pool, self.workspace.id)
            .await?
            .into_iter()
            .map(|session| session.id)
            .collect::<Vec<_>>();
        let repo_paths = repositories
            .iter()
            .map(|repo| repo.path.clone())
            .collect::<Vec<_>>();

        Ok(WorkspaceDeletionContext {
            workspace_id: self.workspace.id,
            branch_name: self.workspace.branch.clone(),
            workspace_dir: self.workspace.container_ref.clone().map(PathBuf::from),
            repositories,
            repo_paths,
            session_ids,
        })
    }

    pub async fn delete_record(&self) -> Result<u64, sqlx::Error> {
        DbWorkspace::delete(&self.db.pool, self.workspace.id).await
    }
}

#[derive(Clone)]
pub struct WorkspaceManager {
    db: DBService,
}

impl WorkspaceManager {
    const LEGACY_WORKSPACE_DIR_NAME: &'static str = ".vibe-kanban-workspaces";
    const WORKSPACE_MARKER_FILE_NAME: &'static str = ".vibe-kanban-workspace";

    pub fn new(db: DBService) -> Self {
        Self { db }
    }

    pub async fn load_managed_workspace(
        &self,
        workspace: DbWorkspace,
    ) -> Result<ManagedWorkspace, sqlx::Error> {
        let repos =
            WorkspaceRepo::find_repos_with_target_branch_for_workspace(&self.db.pool, workspace.id)
                .await?;
        Ok(ManagedWorkspace::new(self.db.clone(), workspace, repos))
    }

    pub fn spawn_workspace_deletion_cleanup(
        context: WorkspaceDeletionContext,
        delete_branches: bool,
    ) {
        tokio::spawn(async move {
            let WorkspaceDeletionContext {
                workspace_id,
                branch_name,
                workspace_dir,
                repositories,
                repo_paths,
                session_ids,
            } = context;

            for session_id in session_ids {
                if let Err(e) = Self::remove_session_process_logs(session_id).await {
                    warn!(
                        "Failed to remove filesystem process logs for session {}: {}",
                        session_id, e
                    );
                }
            }

            if let Some(workspace_dir) = workspace_dir {
                info!(
                    "Starting background cleanup for workspace {} at {}",
                    workspace_id,
                    workspace_dir.display()
                );

                if let Err(e) = Self::cleanup_workspace(&workspace_dir, &repositories).await {
                    error!(
                        "Background workspace cleanup failed for {} at {}: {}",
                        workspace_id,
                        workspace_dir.display(),
                        e
                    );
                } else {
                    info!(
                        "Background cleanup completed for workspace {}",
                        workspace_id
                    );
                }
            }

            if delete_branches {
                let git_service = GitService::new();
                for repo_path in repo_paths {
                    match git_service.delete_branch(&repo_path, &branch_name) {
                        Ok(()) => {
                            info!("Deleted branch '{}' from repo {:?}", branch_name, repo_path);
                        }
                        Err(e) => {
                            warn!(
                                "Failed to delete branch '{}' from repo {:?}: {}",
                                branch_name, repo_path, e
                            );
                        }
                    }
                }
            }
        });
    }

    async fn remove_session_process_logs(session_id: Uuid) -> Result<(), std::io::Error> {
        let dir = utils::execution_logs::process_logs_session_dir(session_id);
        match tokio::fs::remove_dir_all(&dir).await {
            Ok(()) => Ok(()),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
            Err(e) => Err(e),
        }
    }

    /// Create a workspace with worktrees for all repositories.
    /// On failure, rolls back any already-created worktrees.
    pub async fn create_workspace(
        workspace_dir: &Path,
        repos: &[RepoWorkspaceInput],
        branch_name: &str,
    ) -> Result<WorktreeContainer, WorkspaceError> {
        if repos.is_empty() {
            return Err(WorkspaceError::NoRepositories);
        }

        info!(
            "Creating workspace at {} with {} repositories",
            workspace_dir.display(),
            repos.len()
        );

        tokio::fs::create_dir_all(workspace_dir).await?;

        let mut created_worktrees: Vec<RepoWorktree> = Vec::new();

        for input in repos {
            let worktree_path = workspace_dir.join(&input.repo.name);

            debug!(
                "Creating worktree for repo '{}' at {}",
                input.repo.name,
                worktree_path.display()
            );

            match WorktreeManager::create_worktree(
                &input.repo.path,
                branch_name,
                &worktree_path,
                &input.target_branch,
                true,
            )
            .await
            {
                Ok(()) => {
                    created_worktrees.push(RepoWorktree {
                        repo_id: input.repo.id,
                        repo_name: input.repo.name.clone(),
                        source_repo_path: input.repo.path.clone(),
                        worktree_path,
                    });
                }
                Err(e) => {
                    error!(
                        "Failed to create worktree for repo '{}': {}. Rolling back...",
                        input.repo.name, e
                    );

                    // Rollback: cleanup all worktrees we've created so far
                    Self::cleanup_created_worktrees(&created_worktrees).await;

                    // Also remove the workspace directory if it's empty
                    if let Err(cleanup_err) = tokio::fs::remove_dir(workspace_dir).await {
                        debug!(
                            "Could not remove workspace dir during rollback: {}",
                            cleanup_err
                        );
                    }

                    return Err(WorkspaceError::PartialCreation(format!(
                        "Failed to create worktree for repo '{}': {}",
                        input.repo.name, e
                    )));
                }
            }
        }

        info!(
            "Successfully created workspace with {} worktrees",
            created_worktrees.len()
        );

        Self::ensure_workspace_marker(workspace_dir).await?;

        Ok(WorktreeContainer {
            workspace_dir: workspace_dir.to_path_buf(),
            worktrees: created_worktrees,
        })
    }

    /// Ensure all worktrees in a workspace exist (for cold restart scenarios)
    pub async fn ensure_workspace_exists(
        workspace_dir: &Path,
        repos: &[RepoWorkspaceInput],
        branch_name: &str,
    ) -> Result<(), WorkspaceError> {
        if repos.is_empty() {
            return Err(WorkspaceError::NoRepositories);
        }

        // Try legacy migration first (single repo projects only)
        // Old layout had worktree directly at workspace_dir; new layout has it at workspace_dir/{repo_name}
        if repos.len() == 1 && Self::migrate_legacy_worktree(workspace_dir, &repos[0].repo).await? {
            Self::ensure_workspace_marker(workspace_dir).await?;
            return Ok(());
        }

        if !workspace_dir.exists() {
            tokio::fs::create_dir_all(workspace_dir).await?;
        }

        let git = GitService::new();

        for input in repos {
            let repo = &input.repo;
            let worktree_path = workspace_dir.join(&repo.name);

            debug!(
                "Ensuring worktree exists for repo '{}' at {}",
                repo.name,
                worktree_path.display()
            );

            if git.check_branch_exists(&repo.path, branch_name)? {
                WorktreeManager::ensure_worktree_exists(&repo.path, branch_name, &worktree_path)
                    .await?;
            } else {
                info!(
                    "Workspace branch '{}' missing in repo '{}'; creating from target branch '{}'",
                    branch_name, repo.name, input.target_branch
                );
                WorktreeManager::create_worktree(
                    &repo.path,
                    branch_name,
                    &worktree_path,
                    &input.target_branch,
                    true,
                )
                .await?;
            }
        }

        Self::ensure_workspace_marker(workspace_dir).await?;

        Ok(())
    }

    /// Clean up all worktrees in a workspace
    pub async fn cleanup_workspace(
        workspace_dir: &Path,
        repos: &[Repo],
    ) -> Result<(), WorkspaceError> {
        info!("Cleaning up workspace at {}", workspace_dir.display());

        let cleanup_data: Vec<WorktreeCleanup> = repos
            .iter()
            .map(|repo| {
                let worktree_path = workspace_dir.join(&repo.name);
                WorktreeCleanup::new(worktree_path, Some(repo.path.clone()))
            })
            .collect();

        WorktreeManager::batch_cleanup_worktrees(&cleanup_data).await?;

        // Remove the workspace directory itself
        if workspace_dir.exists()
            && let Err(e) = tokio::fs::remove_dir_all(workspace_dir).await
        {
            debug!(
                "Could not remove workspace directory {}: {}",
                workspace_dir.display(),
                e
            );
        }

        Ok(())
    }

    /// Get the base directory for workspaces (same as worktree base dir)
    pub fn get_workspace_base_dir() -> PathBuf {
        WorktreeManager::get_worktree_base_dir()
    }

    /// Migrate a legacy single-worktree layout to the new workspace layout.
    /// Old layout: workspace_dir IS the worktree
    /// New layout: workspace_dir contains worktrees at workspace_dir/{repo_name}
    ///
    /// Returns Ok(true) if migration was performed, Ok(false) if no migration needed.
    async fn migrate_legacy_worktree(
        workspace_dir: &Path,
        repo: &Repo,
    ) -> Result<bool, WorkspaceError> {
        let expected_worktree_path = workspace_dir.join(&repo.name);

        // Detect old-style: workspace_dir exists AND has .git file (worktree marker)
        // AND expected new location doesn't exist
        let git_file = workspace_dir.join(".git");
        let is_old_style = workspace_dir.exists()
            && git_file.exists()
            && git_file.is_file() // .git file = worktree, .git dir = main repo
            && !expected_worktree_path.exists();

        if !is_old_style {
            return Ok(false);
        }

        info!(
            "Detected legacy worktree at {}, migrating to new layout",
            workspace_dir.display()
        );

        // Move old worktree to temp location (can't move into subdirectory of itself)
        let temp_name = format!(
            "{}-migrating",
            workspace_dir
                .file_name()
                .map(|n| n.to_string_lossy())
                .unwrap_or_default()
        );
        let temp_path = workspace_dir.with_file_name(temp_name);

        WorktreeManager::move_worktree(&repo.path, workspace_dir, &temp_path).await?;

        // Create new workspace directory
        tokio::fs::create_dir_all(workspace_dir).await?;

        // Move worktree to final location using git worktree move
        WorktreeManager::move_worktree(&repo.path, &temp_path, &expected_worktree_path).await?;

        if temp_path.exists() {
            let _ = tokio::fs::remove_dir_all(&temp_path).await;
        }

        info!(
            "Successfully migrated legacy worktree to {}",
            expected_worktree_path.display()
        );

        Ok(true)
    }

    /// Helper to cleanup worktrees during rollback
    async fn cleanup_created_worktrees(worktrees: &[RepoWorktree]) {
        for worktree in worktrees {
            let cleanup = WorktreeCleanup::new(
                worktree.worktree_path.clone(),
                Some(worktree.source_repo_path.clone()),
            );

            if let Err(e) = WorktreeManager::cleanup_worktree(&cleanup).await {
                error!(
                    "Failed to cleanup worktree '{}' during rollback: {}",
                    worktree.repo_name, e
                );
            }
        }
    }

    pub async fn cleanup_orphan_workspaces(&self) {
        if std::env::var("DISABLE_WORKTREE_CLEANUP").is_ok() {
            info!(
                "Orphan workspace cleanup is disabled via DISABLE_WORKTREE_CLEANUP environment variable"
            );
            return;
        }

        // Always clean up the default directory
        let default_dir = WorktreeManager::get_default_worktree_base_dir();
        self.cleanup_orphans_in_directory(&default_dir, false).await;

        // Also clean up custom directory if it's different from the default
        let current_dir = Self::get_workspace_base_dir();
        if current_dir != default_dir {
            self.cleanup_orphans_in_directory(&current_dir, false).await;
        }
    }

    async fn cleanup_orphans_in_directory(&self, workspace_base_dir: &Path, app_owned_root: bool) {
        let mut directories_to_scan = vec![(workspace_base_dir.to_path_buf(), app_owned_root)];
        let mut legacy_dirs_to_prune = Vec::new();

        while let Some((dir, app_owned_root)) = directories_to_scan.pop() {
            if !dir.exists() {
                debug!(
                    "Workspace base directory {} does not exist, skipping orphan cleanup",
                    dir.display()
                );
                continue;
            }

            let entries = match std::fs::read_dir(&dir) {
                Ok(entries) => entries,
                Err(e) => {
                    error!(
                        "Failed to read workspace base directory {}: {}",
                        dir.display(),
                        e
                    );
                    continue;
                }
            };

            for entry in entries {
                let entry = match entry {
                    Ok(entry) => entry,
                    Err(e) => {
                        warn!("Failed to read directory entry: {}", e);
                        continue;
                    }
                };

                let path = entry.path();
                if !path.is_dir() {
                    continue;
                }

                if path.file_name().and_then(|name| name.to_str())
                    == Some(Self::LEGACY_WORKSPACE_DIR_NAME)
                {
                    legacy_dirs_to_prune.push(path.clone());
                    directories_to_scan.push((path, true));
                    continue;
                }

                if !app_owned_root && !Self::has_workspace_marker(&path) {
                    debug!(
                        "Skipping unmarked directory during orphan cleanup: {}",
                        path.display()
                    );
                    continue;
                }

                let workspace_path_str = path.to_string_lossy().to_string();
                let has_tracked_workspace =
                    match DbWorkspace::container_ref_exists(&self.db.pool, &workspace_path_str)
                        .await
                    {
                        Ok(exists) => exists,
                        Err(e) => {
                            warn!(
                                "Failed to check tracked workspace path {}: {}",
                                workspace_path_str, e
                            );
                            continue;
                        }
                    };

                if !has_tracked_workspace {
                    info!("Found orphaned workspace: {}", workspace_path_str);
                    if let Err(e) = Self::cleanup_workspace_without_repos(&path).await {
                        error!(
                            "Failed to remove orphaned workspace {}: {}",
                            workspace_path_str, e
                        );
                    } else {
                        info!(
                            "Successfully removed orphaned workspace: {}",
                            workspace_path_str
                        );
                    }
                }
            }
        }

        for legacy_dir in legacy_dirs_to_prune.into_iter().rev() {
            Self::remove_empty_legacy_workspace_dir(&legacy_dir).await;
        }
    }

    async fn ensure_workspace_marker(workspace_dir: &Path) -> Result<(), WorkspaceError> {
        let marker_path = workspace_dir.join(Self::WORKSPACE_MARKER_FILE_NAME);
        if marker_path.exists() {
            return Ok(());
        }

        tokio::fs::write(&marker_path, b"managed by Vibe Kanban\n")
            .await
            .map_err(WorkspaceError::Io)
    }

    fn has_workspace_marker(path: &Path) -> bool {
        path.join(Self::WORKSPACE_MARKER_FILE_NAME).is_file()
    }

    async fn remove_empty_legacy_workspace_dir(path: &Path) {
        let is_empty = match std::fs::read_dir(path) {
            Ok(mut entries) => entries.next().is_none(),
            Err(e) => {
                debug!(
                    "Could not inspect legacy workspace directory {}: {}",
                    path.display(),
                    e
                );
                false
            }
        };

        if is_empty {
            match tokio::fs::remove_dir(path).await {
                Ok(()) => {
                    info!(
                        "Removed empty legacy workspace directory: {}",
                        path.display()
                    );
                }
                Err(e) => {
                    debug!(
                        "Could not remove legacy workspace directory {}: {}",
                        path.display(),
                        e
                    );
                }
            }
        }
    }

    async fn cleanup_workspace_without_repos(workspace_dir: &Path) -> Result<(), WorkspaceError> {
        info!(
            "Cleaning up orphaned workspace at {}",
            workspace_dir.display()
        );

        let entries = match std::fs::read_dir(workspace_dir) {
            Ok(entries) => entries,
            Err(e) => {
                debug!(
                    "Cannot read workspace directory {}, attempting direct removal: {}",
                    workspace_dir.display(),
                    e
                );
                return tokio::fs::remove_dir_all(workspace_dir)
                    .await
                    .map_err(WorkspaceError::Io);
            }
        };

        for entry in entries.filter_map(|e| e.ok()) {
            let path = entry.path();
            if path.is_dir()
                && let Err(e) = WorktreeManager::cleanup_suspected_worktree(&path).await
            {
                warn!("Failed to cleanup suspected worktree: {}", e);
            }
        }

        if workspace_dir.exists()
            && let Err(e) = tokio::fs::remove_dir_all(workspace_dir).await
        {
            debug!(
                "Could not remove workspace directory {}: {}",
                workspace_dir.display(),
                e
            );
        }

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use std::path::PathBuf;

    use uuid::Uuid;

    use super::WorkspaceManager;

    fn temp_workspace_dir() -> PathBuf {
        std::env::temp_dir().join(format!("vk-workspace-manager-test-{}", Uuid::new_v4()))
    }

    #[tokio::test]
    async fn ensure_workspace_marker_creates_marker_file() {
        let workspace_dir = temp_workspace_dir();
        tokio::fs::create_dir_all(&workspace_dir).await.unwrap();

        WorkspaceManager::ensure_workspace_marker(&workspace_dir)
            .await
            .unwrap();

        assert!(WorkspaceManager::has_workspace_marker(&workspace_dir));

        tokio::fs::remove_dir_all(&workspace_dir).await.unwrap();
    }
}
