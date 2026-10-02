---
name: 🐛 Bug Report
about: Report a bug to help us improve the Drone Detector System
title: '[BUG] '
labels: bug, needs-triage
assignees: ''

---

## 🐛 Bug Description

<!-- A clear and concise description of what the bug is. -->

**Expected behavior:**
<!-- What did you expect to happen? -->

**Actual behavior:**
<!-- What actually happened? -->

**Screenshots/Logs:**
<!-- If applicable, add screenshots or logs to help explain your problem. -->

## 🔄 Steps to Reproduce

<!-- Steps to reproduce the behavior: -->
1. Run command '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

## 📋 Environment

**Drone Detector Version:**
<!-- e.g., v1.0.0, or commit hash -->

**Deployment Method:**
- [ ] Docker Compose
- [ ] Kubernetes
- [ ] Bare Metal
- [ ] Development

**Operating System:**
<!-- e.g., Ubuntu 22.04, Windows 11, macOS 14 -->

**Python Version:**
<!-- e.g., 3.11.5 -->

**SDR Hardware:**
<!-- e.g., HackRF One, RTL-SDR v3, ADALM-PLUTO, or None for mock mode -->

## 📊 System Information

<details>
<summary>System Details</summary>

```bash
# Run these commands and paste output:

# OS Information
uname -a
cat /etc/os-release

# Python version
python --version
pip --version

# Docker version (if applicable)
docker --version
docker-compose --version

# SDR device info
hackrf_info 2>/dev/null || rtl_test -t 2>/dev/null || echo "No SDR detected"

# Memory and CPU
free -h
nproc
</details>
🔍 Logs
<details> <summary>Relevant Logs</summary>
bash
# Paste relevant logs here (API logs, worker logs, etc.)
# For Docker deployments:
docker-compose logs --tail=100

# For bare metal:
tail -100 /var/log/drone-detector/system.log
tail -100 /var/log/drone-detector/api.log
</details>
⚙️ Configuration
<details> <summary>Configuration (redact sensitive data)</summary>
yaml
# Paste relevant configuration (config/system.yaml, .env, etc.)
# Remove passwords, API keys, and other sensitive information
</details>
📎 Additional Context
<!-- Add any other context about the problem here, such as frequency of occurrence, recent changes, etc. -->
🩺 Diagnostic Information
bash
# Run diagnostic script and paste output:
python scripts/diagnostics.py
🚦 Severity Assessment
Critical: System crash, data loss, security breach

High: Major feature broken, significant performance degradation

Medium: Feature partially broken, annoying bug

Low: Minor issue, documentation error

🔬 Possible Cause/Solution
<!-- If you have any idea what might be causing the issue or how to fix it, please share. -->
✅ Checklist
I have searched for similar issues (including closed ones)

I have updated to the latest version

I have provided clear steps to reproduce

I have included relevant logs and configuration

I have run the diagnostic script

I have checked the troubleshooting guide

📞 Additional Contact
<!-- Optional: How can we contact you for more information? -->
Discord: @username

Email: (only if you're comfortable sharing)

text

Here's also a `config.yml` for the issue templates (optional but helpful):

```yaml
# .github/ISSUE_TEMPLATE/config.yml
blank_issues_enabled: false
contact_links:
  - name: 📚 Documentation
    url: https://docs.drone-detector.com
    about: Check the documentation before opening an issue
  - name: 💬 Discord Community
    url: https://discord.gg/drone-detector
    about: Ask questions and discuss with the community
  - name: ❓ GitHub Discussions
    url: https://github.com/drone-detector/drone-detector/discussions
    about: Ask questions and share ideas
  - name: 📖 Troubleshooting Guide
    url: https://docs.drone-detector.com/troubleshooting
    about: Common issues and solutions
  - name: 🔒 Security Issue
    url: https://github.com/drone-detector/drone-detector/security/policy
    about: Please report security vulnerabilities here
This bug report template provides:

Structured Sections:

Clear bug description with expected/actual behavior

Steps to reproduce

Environment information

System Information:

Version and deployment method

Operating system and Python version

SDR hardware details

Diagnostic Tools:

Commands to collect system info

Log collection instructions

Diagnostic script output

Configuration:

Collapsible sections for logs and config

Reminder to redact sensitive data

Severity Assessment:

Self-assessment of impact level

Helps with prioritization

Checklist:

Ensures users have tried basic troubleshooting

Promotes quality bug reports

Additional Resources:

Links to documentation, Discord, discussions

Security reporting instructions

The template guides users to provide comprehensive information that helps maintainers quickly understand, reproduce, and fix issues.
