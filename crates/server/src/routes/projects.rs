use std::collections::{HashMap, HashSet};

use axum::{
    Json, Router,
    extract::{Path, State},
    response::Json as ResponseJson,
    routing::get,
};
use db::models::{
    project::Project,
    repo::Repo,
    scratch::{Scratch, ScratchPayload, ScratchType},
    workspace_repo::RepoWithTargetBranch,
};
use deployment::Deployment;
use serde::Deserialize;
use utils::response::ApiResponse;
use uuid::Uuid;

use crate::{DeploymentImpl, error::ApiError};

fn normalize_project_name(name: &str) -> String {
    name.trim().to_ascii_lowercase()
}

fn project_name_key(name: &str) -> String {
    normalize_project_name(name)
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric())
        .collect()
}

#[derive(Debug, Clone)]
struct SyntheticProject {
    project: Project,
    repo_ids: Vec<Uuid>,
}

const SUB_AGENTS_REPO_NAME_HINTS: &[&str] = &[
    "subagent",
    "subagents",
    "subagentsrepo",
    "sub-agent",
    "sub-agents",
    "sub_agent",
    "sub agent",
    "vk-subagent-monitor",
];

fn is_sub_agents_repo(repo: &Repo) -> bool {
    let matches_hint = |value: &str| {
        let normalized = normalize_project_name(value);
        SUB_AGENTS_REPO_NAME_HINTS
            .iter()
            .any(|hint| normalized.contains(hint))
    };

    matches_hint(&repo.name)
        || matches_hint(&repo.display_name)
        || matches_hint(&repo.path.to_string_lossy())
}

fn synthetic_project_from_repo(repo: &Repo) -> Project {
    Project {
        id: repo.id,
        name: repo.display_name.clone(),
        archived: false,
        default_agent_working_dir: repo.default_working_dir.clone(),
        remote_project_id: None,
        created_at: repo.created_at,
        updated_at: repo.updated_at,
    }
}

async fn list_sub_agents_repo_projects(
    deployment: &DeploymentImpl,
) -> Result<Vec<Project>, ApiError> {
    let repos = Repo::list_all(&deployment.db().pool).await?;
    let mut synthetic_projects = repos
        .into_iter()
        .filter(is_sub_agents_repo)
        .map(|repo| synthetic_project_from_repo(&repo))
        .collect::<Vec<_>>();

    synthetic_projects.sort_by(|left, right| {
        right
            .updated_at
            .cmp(&left.updated_at)
            .then_with(|| left.name.cmp(&right.name))
    });

    Ok(synthetic_projects)
}

#[derive(Debug, Deserialize)]
struct UpdateProjectRequest {
    name: Option<String>,
    archived: Option<bool>,
}

async fn list_synthetic_projects(
    deployment: &DeploymentImpl,
) -> Result<Vec<SyntheticProject>, ApiError> {
    let scratches = Scratch::find_all(&deployment.db().pool).await?;
    let mut synthetic_projects = Vec::new();

    for scratch in scratches {
        let repo_ids = match scratch.payload {
            ScratchPayload::ProjectRepoDefaults(data) => data
                .repos
                .into_iter()
                .map(|repo| repo.repo_id)
                .collect::<Vec<_>>(),
            _ => continue,
        };

        if repo_ids.is_empty() {
            continue;
        }

        let repos = Repo::find_by_ids(&deployment.db().pool, &repo_ids).await?;
        let Some(primary_repo) = repos.first() else {
            continue;
        };

        synthetic_projects.push(SyntheticProject {
            project: Project {
                id: scratch.id,
                name: primary_repo.display_name.clone(),
                archived: false,
                default_agent_working_dir: primary_repo.default_working_dir.clone(),
                remote_project_id: None,
                created_at: scratch.created_at,
                updated_at: scratch.updated_at,
            },
            repo_ids,
        });
    }

    synthetic_projects.sort_by(|left, right| {
        compare_projects_for_synthetic_display(&left.project, &right.project)
    });

    Ok(synthetic_projects)
}

async fn find_exact_synthetic_project(
    deployment: &DeploymentImpl,
    project_id: Uuid,
) -> Result<Option<Project>, ApiError> {
    let Some(scratch) = Scratch::find_by_id(
        &deployment.db().pool,
        project_id,
        &ScratchType::ProjectRepoDefaults,
    )
    .await?
    else {
        return Ok(None);
    };

    let repo_ids = match scratch.payload {
        ScratchPayload::ProjectRepoDefaults(data) => data
            .repos
            .into_iter()
            .map(|repo| repo.repo_id)
            .collect::<Vec<_>>(),
        _ => return Ok(None),
    };
    if repo_ids.is_empty() {
        return Ok(None);
    }

    let repos = Repo::find_by_ids(&deployment.db().pool, &repo_ids).await?;
    let Some(primary_repo) = repos.first() else {
        return Ok(None);
    };

    Ok(Some(Project {
        id: scratch.id,
        name: primary_repo.display_name.clone(),
        archived: false,
        default_agent_working_dir: primary_repo.default_working_dir.clone(),
        remote_project_id: None,
        created_at: scratch.created_at,
        updated_at: scratch.updated_at,
    }))
}

async fn find_named_synthetic_project(
    deployment: &DeploymentImpl,
    project_name: &str,
) -> Result<Option<Project>, ApiError> {
    let synthetic_projects = list_synthetic_projects(deployment).await?;
    let target_name = project_name_key(project_name);
    Ok(synthetic_projects
        .into_iter()
        .map(|synthetic_project| synthetic_project.project)
        .find(|project| project_name_key(&project.name) == target_name))
}

fn enrich_with_synthetic_project(project: &mut Project, synthetic_project: &Project) {
    if project.default_agent_working_dir.is_none() {
        project.default_agent_working_dir = synthetic_project.default_agent_working_dir.clone();
    }
}

fn compare_projects_for_synthetic_display(left: &Project, right: &Project) -> std::cmp::Ordering {
    right
        .updated_at
        .cmp(&left.updated_at)
        .then_with(|| left.name.cmp(&right.name))
        .then_with(|| left.id.cmp(&right.id))
}

fn sort_synthetic_projects_for_display(projects: &mut [Project]) {
    projects.sort_by(|left, right| compare_projects_for_synthetic_display(left, right));
}

fn filter_synthetic_project_candidates(
    synthetic_projects: &[SyntheticProject],
    existing_ids: &HashSet<Uuid>,
    existing_names: &HashSet<String>,
    existing_repo_ids: &HashSet<Uuid>,
) -> Vec<Project> {
    let mut candidates = synthetic_projects
        .iter()
        .filter(|synthetic_project| {
            let project = &synthetic_project.project;
            !existing_ids.contains(&project.id)
                && !existing_names.contains(&project_name_key(&project.name))
                && !synthetic_project
                    .repo_ids
                    .iter()
                    .any(|repo_id| existing_repo_ids.contains(repo_id))
        })
        .map(|synthetic_project| synthetic_project.project.clone())
        .collect::<Vec<_>>();
    sort_synthetic_projects_for_display(&mut candidates);
    candidates
}

async fn list_projects(
    State(deployment): State<DeploymentImpl>,
) -> Result<ResponseJson<ApiResponse<Vec<Project>>>, ApiError> {
    let mut projects = Project::find_all(&deployment.db().pool).await?;
    let synthetic_projects = list_synthetic_projects(&deployment).await?;
    let sub_agents_projects = list_sub_agents_repo_projects(&deployment).await?;
    let synthetic_by_name = synthetic_projects
        .iter()
        .map(|synthetic_project| {
            (
                project_name_key(&synthetic_project.project.name),
                synthetic_project.project.clone(),
            )
        })
        .collect::<HashMap<_, _>>();
    let synthetic_by_name = sub_agents_projects.iter().cloned().fold(
        synthetic_by_name,
        |mut synthetic_by_name, project| {
            let key = project_name_key(&project.name);
            synthetic_by_name.entry(key).or_insert(project);
            synthetic_by_name
        },
    );

    let mut existing_names = projects
        .iter()
        .map(|project| project_name_key(&project.name))
        .collect::<HashSet<_>>();
    let mut existing_ids = projects
        .iter()
        .map(|project| project.id)
        .collect::<HashSet<_>>();
    let existing_repo_ids = sqlx::query_scalar::<_, Uuid>("SELECT repo_id FROM project_repos")
        .fetch_all(&deployment.db().pool)
        .await?
        .into_iter()
        .collect::<HashSet<_>>();

    let mut synthetic_candidates = filter_synthetic_project_candidates(
        &synthetic_projects,
        &existing_ids,
        &existing_names,
        &existing_repo_ids,
    );
    synthetic_candidates.extend(sub_agents_projects);
    sort_synthetic_projects_for_display(&mut synthetic_candidates);

    for project in &synthetic_candidates {
        let id_exists = existing_ids.contains(&project.id);
        let name_exists = existing_names.contains(&project_name_key(&project.name));

        if !id_exists && !name_exists {
            projects.push(project.clone());
            existing_ids.insert(project.id);
            existing_names.insert(project_name_key(&project.name));
        }
    }

    for project in &mut projects {
        if let Some(synthetic_project) = synthetic_by_name.get(&project_name_key(&project.name)) {
            enrich_with_synthetic_project(project, synthetic_project);
        }
    }

    Ok(ResponseJson(ApiResponse::success(projects)))
}

async fn get_project(
    State(deployment): State<DeploymentImpl>,
    Path(project_id): Path<Uuid>,
) -> Result<ResponseJson<ApiResponse<Project>>, ApiError> {
    let project = match Project::find_by_id(&deployment.db().pool, project_id).await {
        Ok(mut project) => {
            if let Some(synthetic_project) =
                find_named_synthetic_project(&deployment, &project.name).await?
            {
                enrich_with_synthetic_project(&mut project, &synthetic_project);
            }
            project
        }
        Err(sqlx::Error::RowNotFound) => {
            if let Some(repo) = Repo::find_by_id(&deployment.db().pool, project_id).await?
                && is_sub_agents_repo(&repo)
            {
                synthetic_project_from_repo(&repo)
            } else {
                find_exact_synthetic_project(&deployment, project_id)
                    .await?
                    .ok_or(sqlx::Error::RowNotFound)?
            }
        }
        Err(error) => return Err(error.into()),
    };

    Ok(ResponseJson(ApiResponse::success(project)))
}

fn repo_default_target_branch(repo: &Repo) -> String {
    repo.default_target_branch
        .clone()
        .unwrap_or_else(|| "main".to_string())
}

async fn list_project_repos(
    State(deployment): State<DeploymentImpl>,
    Path(project_id): Path<Uuid>,
) -> Result<ResponseJson<ApiResponse<Vec<RepoWithTargetBranch>>>, ApiError> {
    let repo_ids = if let Some(scratch) = Scratch::find_by_id(
        &deployment.db().pool,
        project_id,
        &ScratchType::ProjectRepoDefaults,
    )
    .await?
    {
        match scratch.payload {
            ScratchPayload::ProjectRepoDefaults(data) => data
                .repos
                .into_iter()
                .map(|repo| (repo.repo_id, Some(repo.target_branch)))
                .collect::<Vec<_>>(),
            _ => Vec::new(),
        }
    } else {
        if let Some(repo) = Repo::find_by_id(&deployment.db().pool, project_id).await?
            && is_sub_agents_repo(&repo)
        {
            let target_branch = repo_default_target_branch(&repo);
            return Ok(ResponseJson(ApiResponse::success(vec![
                RepoWithTargetBranch {
                    repo,
                    target_branch,
                },
            ])));
        }

        let ids = sqlx::query_scalar::<_, Uuid>(
            r#"SELECT repo_id
               FROM project_repos
               WHERE project_id = ?
               ORDER BY rowid ASC"#,
        )
        .bind(project_id)
        .fetch_all(&deployment.db().pool)
        .await?;

        ids.into_iter().map(|repo_id| (repo_id, None)).collect()
    };

    let ids = repo_ids
        .iter()
        .map(|(repo_id, _)| *repo_id)
        .collect::<Vec<_>>();
    let repos = Repo::find_by_ids(&deployment.db().pool, &ids).await?;
    let target_by_repo_id = repo_ids.into_iter().collect::<HashMap<_, _>>();

    let repos = repos
        .into_iter()
        .map(|repo| {
            let target_branch = target_by_repo_id
                .get(&repo.id)
                .and_then(|target_branch| target_branch.clone())
                .unwrap_or_else(|| repo_default_target_branch(&repo));

            RepoWithTargetBranch {
                repo,
                target_branch,
            }
        })
        .collect::<Vec<_>>();

    Ok(ResponseJson(ApiResponse::success(repos)))
}

async fn update_project(
    State(deployment): State<DeploymentImpl>,
    Path(project_id): Path<Uuid>,
    Json(payload): Json<UpdateProjectRequest>,
) -> Result<ResponseJson<ApiResponse<Project>>, ApiError> {
    let name = payload.name.as_deref().map(str::trim);
    if name.is_some_and(str::is_empty) {
        return Err(ApiError::BadRequest(
            "Project name cannot be empty".to_string(),
        ));
    }

    let project =
        Project::update_details(&deployment.db().pool, project_id, name, payload.archived).await?;
    Ok(ResponseJson(ApiResponse::success(project)))
}

pub fn router() -> Router<DeploymentImpl> {
    let inner = Router::new()
        .route("/", get(list_projects))
        .route("/{project_id}", get(get_project).patch(update_project))
        .route("/{project_id}/repos", get(list_project_repos));

    Router::new().nest("/projects", inner)
}

#[cfg(test)]
mod tests {
    use std::collections::HashSet;

    use chrono::{TimeZone, Utc};
    use db::models::project::Project;
    use uuid::Uuid;

    use super::{
        SyntheticProject, filter_synthetic_project_candidates, project_name_key,
        sort_synthetic_projects_for_display,
    };

    fn project(id: &str, name: &str, updated_second: u32) -> Project {
        let timestamp = Utc
            .with_ymd_and_hms(2026, 6, 3, 1, 0, updated_second)
            .single()
            .expect("valid timestamp");

        Project {
            id: Uuid::parse_str(id).expect("valid uuid"),
            name: name.to_string(),
            archived: false,
            default_agent_working_dir: None,
            remote_project_id: None,
            created_at: timestamp,
            updated_at: timestamp,
        }
    }

    #[test]
    fn synthetic_projects_have_stable_display_order() {
        let mut projects = vec![
            project("33333333-3333-3333-3333-333333333333", "Charlie", 10),
            project("22222222-2222-2222-2222-222222222222", "Bravo", 20),
            project("11111111-1111-1111-1111-111111111111", "Alpha", 20),
        ];

        sort_synthetic_projects_for_display(&mut projects);

        let names = projects
            .into_iter()
            .map(|project| project.name)
            .collect::<Vec<_>>();
        assert_eq!(names, vec!["Alpha", "Bravo", "Charlie"]);
    }

    #[test]
    fn project_name_key_matches_kebab_and_camel_variants() {
        assert_eq!(
            project_name_key("foxtrot-lima"),
            project_name_key("FoxtrotLima")
        );
        assert_eq!(
            project_name_key("intake-shield"),
            project_name_key("intakeShield")
        );
    }

    #[test]
    fn synthetic_project_is_hidden_when_repo_belongs_to_real_project() {
        let repo_id = Uuid::parse_str("99999999-9999-9999-9999-999999999999").expect("valid uuid");
        let synthetic_project = SyntheticProject {
            project: project("77777777-7777-7777-7777-777777777777", "FoxtrotLima", 20),
            repo_ids: vec![repo_id],
        };
        let existing_names = HashSet::from([project_name_key("foxtrot-lima")]);
        let existing_repo_ids = HashSet::from([repo_id]);

        let candidates = filter_synthetic_project_candidates(
            &[synthetic_project],
            &HashSet::new(),
            &existing_names,
            &existing_repo_ids,
        );

        assert!(candidates.is_empty());
    }

    #[test]
    fn synthetic_only_project_is_kept() {
        let synthetic_project = SyntheticProject {
            project: project(
                "88888888-8888-8888-8888-888888888888",
                "VK Sub-Agent Monitor",
                20,
            ),
            repo_ids: vec![
                Uuid::parse_str("99999999-9999-9999-9999-999999999999").expect("valid uuid"),
            ],
        };

        let candidates = filter_synthetic_project_candidates(
            &[synthetic_project],
            &HashSet::new(),
            &HashSet::new(),
            &HashSet::new(),
        );

        assert_eq!(candidates.len(), 1);
        assert_eq!(candidates[0].name, "VK Sub-Agent Monitor");
    }
}
