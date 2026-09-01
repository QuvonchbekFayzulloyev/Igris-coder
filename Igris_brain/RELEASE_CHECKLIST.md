# IGRIS Release Checklist

Use this checklist before every release to ensure quality and completeness.

## Quick Start

```bash
# Run the release script
python release.py --version 1.3.0

# Or step by step
python version_bumper.py bump minor --dry-run
python changelog_generator.py generate --version 1.3.0
python version_bumper.py bump minor --tag --commit
```

---

## Pre-Release Checklist

### 1. Code Quality
- [ ] All tests passing
  ```bash
  python -m pytest test_*.py -v
  ```
- [ ] No linting errors
  ```bash
  python -m flake8 --max-line-length=120
  ```
- [ ] Type checking passed
  ```bash
  python -m mypy *.py --ignore-missing-imports
  ```
- [ ] No security vulnerabilities
  ```bash
  pip-audit
  ```

### 2. Documentation
- [ ] README.md updated
- [ ] CHANGELOG.md updated
- [ ] API documentation updated
- [ ] Configuration examples updated
- [ ] Breaking changes documented

### 3. Dependencies
- [ ] requirements.txt updated
- [ ] package.json updated (if applicable)
- [ ] No outdated critical dependencies
- [ ] No known vulnerabilities in dependencies

### 4. Configuration
- [ ] .env.example updated with new variables
- [ ] Config schema validated
- [ ] Default values reviewed
- [ ] Backward compatibility checked

### 5. Testing
- [ ] Unit tests passing
- [ ] Integration tests passing
- [ ] E2E tests passing (if applicable)
- [ ] Manual testing completed
- [ ] Performance benchmarks acceptable

---

## Release Process

### Step 1: Version Bump
```bash
# Check current version
python version_bumper.py current

# Dry run first
python version_bumper.py bump minor --dry-run

# Actually bump
python version_bumper.py bump minor
```

**Version Type Guide:**
- `patch`: Bug fixes (1.2.0 -> 1.2.1)
- `minor`: New features (1.2.0 -> 1.3.0)
- `major`: Breaking changes (1.2.0 -> 2.0.0)
- `pre`: Pre-release (1.2.0 -> 1.2.0-alpha.1)

### Step 2: Generate Changelog
```bash
# Generate changelog
python changelog_generator.py generate --version 1.3.0

# Preview changes
python changelog_generator.py generate --since v1.2.0

# Export to JSON
python changelog_generator.py export --output releases/changelog-1.3.0.json
```

### Step 3: Review Changes
- [ ] Review CHANGELOG.md
- [ ] Verify version numbers in all files
- [ ] Check release notes accuracy
- [ ] Validate breaking changes are documented

### Step 4: Create Release
```bash
# Option A: Manual
git add -A
git commit -m "chore(release): v1.3.0"
git tag -a v1.3.0 -m "Release 1.3.0"
git push origin main --tags

# Option B: Using version bumper
python version_bumper.py bump minor --tag --commit
git push origin main --tags
```

### Step 5: Create GitHub Release
- [ ] Go to GitHub Releases
- [ ] Click "Draft a new release"
- [ ] Select tag `v1.3.0`
- [ ] Set title to "Release 1.3.0"
- [ ] Paste release notes from CHANGELOG.md
- [ ] Upload artifacts (if any)
- [ ] Publish release

---

## Post-Release Checklist

### Immediate (Day 1)
- [ ] Verify release on PyPI/npm (if published)
- [ ] Test installation from package
- [ ] Monitor error tracking (Sentry, etc.)
- [ ] Check deployment status
- [ ] Notify team/stakeholders

### Short-term (Week 1)
- [ ] Monitor user feedback
- [ ] Check for regressions
- [ ] Update documentation if needed
- [ ] Close related issues

### Long-term (Month 1)
- [ ] Review release metrics
- [ ] Document lessons learned
- [ ] Plan next release

---

## Emergency Hotfix Process

For critical bugs that need immediate fix:

```bash
# 1. Create hotfix branch
git checkout -b hotfix/1.3.1 v1.3.0

# 2. Apply fix
# ... make changes ...

# 3. Test
python -m pytest test_*.py -v

# 4. Bump patch version
python version_bumper.py bump patch

# 5. Generate changelog
python changelog_generator.py generate --version 1.3.1

# 6. Merge and tag
git checkout main
git merge hotfix/1.3.1
git tag -a v1.3.1 -m "Hotfix 1.3.1"
git push origin main --tags

# 7. Delete hotfix branch
git branch -d hotfix/1.3.1
```

---

## Release Notes Template

```markdown
# Release X.Y.Z

## 🎉 Highlights
- Feature 1
- Feature 2

## 🚀 New Features
- **scope:** description (#issue)

## 🐛 Bug Fixes
- **scope:** description (#issue)

## ⚠️ Breaking Changes
- Description of breaking change
  - Migration guide: [link]

## 📦 Dependencies
- Updated package from A to B

## 📝 Documentation
- Updated README

## 🔧 Maintenance
- Updated CI/CD pipeline

---

**Full Changelog**: https://github.com/org/igris/compare/vA.B.C...vX.Y.Z
```

---

## Version Numbering Guide

### Semantic Versioning (SemVer)

```
MAJOR.MINOR.PATCH

MAJOR: 1 -> 2
  - Breaking API changes
  - Removed deprecated features
  - Incompatible changes

MINOR: 1.2 -> 1.3
  - New features
  - Backward compatible
  - Optional new functionality

PATCH: 1.2.3 -> 1.2.4
  - Bug fixes
  - Security patches
  - Backward compatible
```

### Pre-release Versions

```
1.0.0-alpha.1   # Internal testing
1.0.0-alpha.2   # Internal testing
1.0.0-beta.1    # External testing
1.0.0-beta.2    # External testing
1.0.0-rc.1      # Release candidate
1.0.0-rc.2      # Release candidate
1.0.0           # Stable release
```

### Build Metadata

```
1.0.0+build.123    # Build number
1.0.0+20240101     # Build date
```

---

## Common Issues & Solutions

### "Version already exists"
```bash
# Delete old tag
git tag -d v1.3.0
git push origin :refs/tags/v1.3.0

# Re-tag
git tag -a v1.3.0 -m "Release 1.3.0"
git push origin v1.3.0
```

### "Tests failing"
```bash
# Run tests with verbose output
python -m pytest test_*.py -v --tb=short

# Fix issues, then re-run
python -m pytest test_*.py -v
```

### "Changelog not updating"
```bash
# Check git history
git log --oneline v1.2.0..HEAD

# Ensure conventional commits
git log --pretty=format:"%s" v1.2.0..HEAD
```

---

## Automation Scripts

```bash
# Full release
python release.py --version 1.3.0 --tag --commit

# Dry run
python release.py --version 1.3.0 --dry-run

# Just changelog
python changelog_generator.py release --version 1.3.0
```

---

*Last updated: 2024*
