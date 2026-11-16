# Organization-level gitStream setup

This package is intended for the special GitHub organization repository named `cm`.

## Contents

- `gitstream.cm` — organization-level advisory AI performance review automation.
- `.github/workflows/gitstream.yml` — the existing generated gitStream workflow copied from the supplied Spring Petclinic repository.
- `performance-review-rules/` — the four performance rule files copied unchanged from the supplied repository.

## Important placement

The organization repository must be named exactly `cm`.

Place `gitstream.cm` at the repository root (NOT in `.cm/`).

Place the workflow at `.github/workflows/gitstream.yml`.

The rules directory must be at the repository root as shown.

## Before enabling

1. Confirm the GitHub organization that owns the repositories (the LinearB integration name `personathon` is not, by itself, proof of the GitHub organization slug).
2. Create `<ORG>/cm` with default branch `main`.
3. Install/enable the gitStream GitHub App on the `cm` repository and on every repository that should receive organization-level automation. The GitStream app's repository access must include `cm`.
4. In LinearB Company Settings > Git, ensure the GitHub integration is connected to gitStream and the `cm` repository is selected/enabled for gitStream.
5. Commit these files to `main`.
6. Ensure the `cm` repository has at least one PR, as required by the GitStream organization setup instructions.
7. Test with a PR to `main` in one consuming repository.

## Advisory-only behavior

The automation uses `code-review@v1` with `approve_on_LGTM: false`. Do not add `gitStream.cm` as a required branch-protection check if you do not want this review to block merging. Keep any existing build/test/security required checks unchanged.

## Migration from the current Spring Petclinic repo

Do not delete local files before central execution is proven.

1. First create and validate `<ORG>/cm`.
2. Test that a PR in Spring Petclinic receives the organization-level AI review.
3. Check for duplicate comments/reviews. The local `.cm/gitstream.cm` currently defines `performance_ai_review`; it can run alongside the central rule because the central automation has a different name.
4. Once central execution works, remove `.cm/gitstream.cm` from Spring Petclinic to prevent duplicate AI reviews. The consuming repository should not need its own `.cm` or `gitstream.yml` for the organization-level automation.
5. The central workflow runs from the `cm` repository on behalf of PR repositories, according to GitStream's organization-level execution model.

## Scope

The rule checks only `.java` and `.cs` files according to the existing combined rules. It is intended to run for non-draft PRs targeting `main`. The rules themselves are copied unchanged from the supplied repository.
