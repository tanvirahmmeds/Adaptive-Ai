# Adaptive Framework CI/CD Workflow

This workflow provides comprehensive CI/CD for the Adaptive Framework including testing, building, skill validation, and automated releases.

## Workflows

### 1. Continuous Integration (`.github/workflows/ci.yml`)
Runs on every push and PR to main branch.

### 2. Skill Validation (`.github/workflows/skill-validation.yml`)
Validates all built-in and user skills.

### 3. Release Automation (`.github/workflows/release.yml`)
Creates releases when all tests pass on main branch.

### 4. Dependency Updates (`.github/workflows/dependabot.yml`)
Automated dependency updates via Dependabot.

---

## Workflow Files

Create these files in your repository: