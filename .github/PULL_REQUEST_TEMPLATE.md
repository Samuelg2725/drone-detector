# Pull Request Template

## 📋 Description

<!-- Provide a clear and concise description of the changes -->

**Related Issue:** Fixes #(issue number)

**Type of Change:**
- [ ] 🐛 Bug fix (non-breaking change)
- [ ] ✨ New feature (non-breaking change)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to change)
- [ ] 📚 Documentation update
- [ ] 🎨 Code refactor
- [ ] ⚡ Performance improvement
- [ ] 🔒 Security fix
- [ ] 🧪 Test update
- [ ] 🔧 Configuration change
- [ ] 📦 Dependency update

## 🎯 Scope of Changes

<!-- Describe which components are affected -->

**Affected Components:**
- [ ] API Layer
- [ ] Domain/Models
- [ ] Infrastructure/Hardware
- [ ] Signal Processing
- [ ] ML/AI Models
- [ ] Database
- [ ] Frontend/UI
- [ ] Documentation
- [ ] CI/CD
- [ ] Docker/Kubernetes
- [ ] Other: ___________

**Hardware Impact:**
- [ ] HackRF One
- [ ] RTL-SDR
- [ ] ADALM-PLUTO
- [ ] Mock Device
- [ ] No hardware impact

## 🧪 Testing

### Test Coverage

- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Hardware tests added/updated (if applicable)
- [ ] Performance benchmarks added/updated (if applicable)
- [ ] E2E tests added/updated (if applicable)

### Testing Commands

```bash
# Run specific tests (update as needed)
pytest tests/path/to/test_file.py -v

# Run all tests
pytest tests/ -v

# Run with coverage
pytest --cov=app --cov-report=html

# Run hardware tests (if applicable)
pytest tests/hardware/ -v -m hardware

# Run performance tests (if applicable)
pytest tests/performance/ -v --benchmark-only
Test Results
<!-- Paste relevant test output here -->
text
Paste test results showing all tests pass
📊 Quality Checks
Code Quality
Code follows project style guide (PEP 8)

Formatted with Black (black .)

Imports sorted with isort (isort .)

Linted with flake8 (flake8 .)

Type checked with mypy (mypy app/)

Security scanned with bandit (bandit -r app/)

Docstrings added for new functions/classes

Comments added for complex logic

Performance Impact
<!-- Describe any performance implications -->
Benchmark Results (if applicable):

bash
# Before change:
# [Insert baseline benchmark results]

# After change:
# [Insert new benchmark results]

# Performance change: +/- ___%
Security Considerations
No hardcoded secrets/credentials

Input validation implemented
Authentication/authorization considered (if API changes)
Sensitive data properly encrypted (if storage changes)
Security headers updated (if web changes)
Dependencies scanned for vulnerabilities

📝 Documentation
Documentation Updates
README.md updated

API documentation updated (if API changes)
Configuration documentation updated
Hardware setup guide updated (if hardware changes)
User guide updated
Architecture docs updated
CHANGELOG.md updated
Migration guide added (if breaking change)
Code Documentation
python
# Example of new function docstring (if applicable)
def new_function(param1: str, param2: int) -> bool:
    """
    Brief description of what this function does.

    Longer description explaining the purpose and any important
    implementation details.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When invalid input is provided

    Example:
        >>> result = new_function("test", 42)
        >>> print(result)
        True
    """
    pass
🔄 Migration Notes
<!-- If this is a breaking change, describe migration steps -->
Breaking Changes:

Change 1: [Description and migration steps]

Change 2: [Description and migration steps]

Database Migrations:

New migration created (alembic revision -m "description")

Migration tested (upgrade and downgrade)

Migration is reversible

Configuration Changes:

yaml
# Old configuration (if applicable)
# ...

# New configuration
# ...
📦 Dependency Changes
<!-- List any new or updated dependencies -->
New Dependencies:

Package	Version	Reason	License
example	1.0.0	Needed for X	MIT
Updated Dependencies:

Package	Old Version	New Version	Reason
example	1.0.0	2.0.0	Security fix
Removed Dependencies:

Package	Reason
example	No longer needed
🖥️ Testing Environment
Local Test Environment:

OS: <!-- e.g., Ubuntu 22.04, macOS 14, Windows 11 -->

Python Version: <!-- e.g., 3.11.5 -->

Hardware: <!-- e.g., HackRF One, or N/A -->

Docker Version: <!-- if applicable -->

Tested Configurations:

Development (mock hardware)

Docker Compose

Kubernetes (if applicable)

Bare metal (if applicable)

Production mode

📸 Screenshots
<!-- If UI changes, add screenshots -->
Before:
https://link-to-before-screenshot

After:
https://link-to-after-screenshot

✅ PR Checklist
<!-- Ensure all items are checked before requesting review -->
Author Checklist
I have read the contributing guidelines

My code follows the project's style guidelines

I have performed a self-review of my code

I have commented my code, particularly in hard-to-understand areas

I have made corresponding changes to the documentation

My changes generate no new warnings

I have added tests that prove my fix is effective or that my feature works

New and existing unit tests pass locally with my changes

Any dependent changes have been merged and published

I have checked my code for security vulnerabilities

I have updated the CHANGELOG.md

I have considered backward compatibility

I have added migration guides for breaking changes

Reviewer Checklist
Code is well-written and follows standards

Tests are comprehensive and meaningful

Documentation is accurate and complete

Security implications considered

Performance impact evaluated

Edge cases handled

No blocking issues found

🚀 Deployment Notes
Deployment Steps (if special handling required):

Rollback Plan:

<!-- Describe how to rollback if deployment fails -->
Monitoring After Deployment:

Check health endpoint: curl http://localhost:8888/health

Monitor error rates for 1 hour

Watch for hardware issues

Verify detection pipeline

📞 Additional Information
<!-- Any additional information that might be useful for reviewers -->
Discussion / RFC: [Link to discussion]

Related PRs: #(PR numbers)

Testing Notes:

<!-- Any specific testing instructions for reviewers -->
🎉 Thank You!
Thank you for contributing to the Drone Detector System! Your efforts help make drone airspace safer for everyone.

<!-- Note to reviewers: Please ensure the author has completed all relevant sections. For small changes (typos, minor docs), you can skip some sections. -->
text

This pull request template provides:

1. **Comprehensive Structure**:
   - Clear description and issue linking
   - Change type classification
   - Scope of changes with component checkboxes
   - Hardware impact assessment

2. **Testing Section**:
   - Test coverage checklist
   - Commands to run specific tests
   - Results placeholder
   - Support for unit, integration, hardware, performance, E2E tests

3. **Quality Checks**:
   - Code quality tools (Black, isort, flake8, mypy, bandit)
   - Performance impact assessment
   - Security considerations checklist

4. **Documentation**:
   - Documentation update checklist
   - Code docstring example
   - Migration notes for breaking changes

5. **Dependency Management**:
   - New, updated, and removed dependencies
   - License information
   - Reason for changes

6. **Testing Environment**:
   - Local environment details
   - Tested configurations
   - OS, Python, hardware versions

7. **Screenshots**:
   - Before/after comparison
   - For UI or visualization changes

8. **Checklists**:
   - Author checklist (pre-review)
   - Reviewer checklist (during review)
   - Ensures thorough review

9. **Deployment Notes**:
   - Special deployment steps
   - Rollback plan
   - Monitoring instructions
   - Health check verification

10. **Additional Information**:
    - Links to discussions/RFCs
    - Related PRs
    - Special testing instructions

The template is comprehensive but allows reviewers to skip sections for small changes (typos, minor docs). It ensures consistent, high-quality pull requests that are well-tested and documented.
