# SWE-Skills

[![skills.sh](https://skills.sh/b/rade-nugroho/SWE-Skills)](https://skills.sh/rade-nugroho/SWE-Skills)

Software Engineer Agent skills.

## Skills

| Skill | What it does |
|---|---|
| [`software-engineer`](skills/software-engineer/SKILL.md) | End-to-end engineering workflow for any code task: size the task, requirements, HLD/LLD when warranted, smallest complete change, test, verify, honest report. Reference files cover system design (architecture styles, scalability, caching, load balancing, consistency, queues, networking, distributed systems, security, CI/CD), LLD, requirements/SRS, testing, debugging & maintenance, UI design, databases, fault tolerance, reliability, metrics, and quality/process. |

## Install

With the [skills CLI](https://skills.sh/docs/cli):

```bash
npx skills add rade-nugroho/SWE-Skills --skill software-engineer
```

Add `-g` to install globally, or `-a claude-code` to pick the agent.

Or as a Claude Code plugin:

```
/plugin marketplace add rade-nugroho/SWE-Skills
/plugin install swe-skills@swe-skills
```

Update the skills CLI install later with:

```bash
npx skills update software-engineer
```

The CLI sends anonymous install telemetry (skill name, skill files, timestamp), which is what lists the repo on skills.sh. Set `DISABLE_TELEMETRY=1` to opt out.

[`skills.sh.json`](skills.sh.json) controls how skills are grouped on the repo's skills.sh page; it does not affect installs.
