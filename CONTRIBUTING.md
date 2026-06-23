# Contributing

Thanks for your interest! This project is managed via Infrastructure-as-Code.
All changes must go through the standard PR process.

## Process

1. Fork the repository
2. Create a feature branch from `main`
3. Make your changes with signed commits
4. Open a Pull Request
5. Get required approvals (1 for standard repos, 2 for infra/lib repos)
6. Wait for status checks to pass
7. Squash-merge when approved

## Requirements

- **Signed commits**: All commits must be GPG or SSH signed
- **Linear history**: Use squash-merge or rebase-merge (no merge commits)
- **CODEOWNERS**: Changes to owned paths require owner review
- **Status checks**: All CI checks must pass

## Repository Management

This repo's settings (branch protection, access, etc.) are managed by
Terraform in the [github-infra](https://github.com/dizhaky/github-infra) repo.
Do not change repo settings via the GitHub UI.
