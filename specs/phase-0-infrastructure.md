# Phase 0: The Iron Foundation — Infrastructure Spec

## Goal

Establish the foundational AWS infrastructure and CI/CD pipeline for the Wealth-Ops v2.0 project using **AWS CDK (Python)**. This phase sets up the "empty stage" that all future phases will build upon.

## Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **IaC Tool** | AWS CDK (Python) | Native Python stack, type-safe, aligns with project standards |
| **DynamoDB Tables** | **Defer to Phase 1.1** | Tables require schema design; foundational infra should be decoupled |
| **Step Functions** | **Defer to Phase 1.2** | Orchestration depends on understanding data flow first |
| **Environments** | `dev` only | Keep scope minimal; prod added when business logic is proven |

---

## Proposed Changes

### CDK Application Structure

#### [NEW] [infra/](file:///Users/radwan/dev/wealth-ops/infra/)

New directory for all CDK infrastructure code:

```
infra/
├── app.py                 # CDK entrypoint
├── cdk.json               # CDK config
├── requirements.txt       # CDK dependencies
└── stacks/
    ├── __init__.py
    └── foundation_stack.py  # Core resources (S3, ECR, IAM)
```

---

### Foundation Stack Resources

#### [NEW] [foundation_stack.py](file:///Users/radwan/dev/wealth-ops/infra/stacks/foundation_stack.py)

| Resource | Type | Purpose |
|----------|------|---------|
| `wealth-ops-data-dev` | S3 Bucket | Store market data, models, artifacts (`{tier}/{asset}.parquet`) |
| `wealth-ops-ecr-dev` | ECR Repository | Docker images for Lambda/Fargate |
| `LambdaExecutionRole` | IAM Role | Shared role for all Lambda functions |
| `FargateTaskRole` | IAM Role | Role for Fargate training tasks |

**S3 Bucket Structure:**
```
wealth-ops-data-dev/
├── raw/           # Raw market data from providers
├── processed/     # Cleaned, gap-filled data
├── models/        # Trained XGBoost models
└── artifacts/     # Backtest results, logs
```

**IAM Policies:**
- Lambda Role: `s3:GetObject`, `s3:PutObject` on data bucket, `dynamodb:*` (for future phases)
- Fargate Role: Same as Lambda + `ecr:GetAuthorizationToken`, `logs:CreateLogStream`

---

### CI/CD Pipeline

#### [NEW] [.github/workflows/ci.yml](file:///Users/radwan/dev/wealth-ops/.github/workflows/ci.yml)

Pipeline for `dev` environment only:

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    - ruff check src/
    - mypy src/ --strict
    - pytest --cov=src --cov-branch --cov-fail-under=100

  cdk-synth:
    - cd infra && cdk synth

  deploy-dev:
    - cd infra && cdk deploy --require-approval never
    # Only runs on push to main, not PRs
```

**Secrets Required:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION` (default: `us-east-1`)

---

### Project Configuration

#### [NEW] [pyproject.toml](file:///Users/radwan/dev/wealth-ops/pyproject.toml)

Poetry project configuration with dev dependencies:

```toml
[tool.poetry]
name = "wealth-ops"
version = "2.0.0"
python = "^3.13"

[tool.poetry.dependencies]
python = "^3.13"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-cov = "^4.1"
mypy = "^1.8"
ruff = "^0.2"
moto = "^5.0"

[tool.poetry.group.infra.dependencies]
aws-cdk-lib = "^2.120"
constructs = "^10.3"

[tool.mypy]
strict = true

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "UP"]
```

---

## Verification Plan

### Automated Tests

Since this is infrastructure-only (no `src/modules/*` code yet), the verification focuses on CDK synthesis and linting:

| Test | Command | Expected Result |
|------|---------|-----------------|
| CDK Synth | `cd infra && cdk synth` | Outputs valid CloudFormation template |
| Ruff Lint | `ruff check infra/` | No errors |
| MyPy Type Check | `mypy infra/ --strict` | No errors |

### Manual Verification

1. **Review CloudFormation Output:** After `cdk synth`, inspect `cdk.out/FoundationStack.template.json` to confirm:
   - S3 bucket has correct naming and tags
   - ECR repository exists
   - IAM roles have expected policies

2. **GitHub Actions Dry Run:** Push a branch and verify the CI workflow triggers and passes the `lint-and-test` + `cdk-synth` jobs (no deploy on PR).

---

## Out of Scope (Deferred)

| Item | Deferred To | Reason |
|------|-------------|--------|
| DynamoDB Tables | Phase 1.1 | Requires schema design |
| Step Functions | Phase 1.2 | Depends on orchestration logic |
| Lambda Functions | Phase 1.2+ | No business logic yet |
| Prod Environment | Phase 4+ | Prove system in dev first |
