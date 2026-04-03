# mypoc - Python Monorepo

A monorepo structure for managing multiple Python proof-of-concept (POC) projects.

## Overview

This workspace is organized as a Python monorepo where different sub-projects can be developed independently while sharing common infrastructure.

## Structure

```
mypoc/
├── projects/          # Directory for all sub-projects
├── docs/              # Documentation and guides
├── README.md          # This file
└── .github/           # GitHub and workspace configuration
```

## Getting Started

1. **Create a new sub-project:**
   ```bash
   mkdir projects/my-project
   cd projects/my-project
   ```

2. **Set up a Python virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Create project files:**
   - `requirements.txt` - Project dependencies
   - `src/` - Source code
   - `tests/` - Unit tests
   - `README.md` - Project documentation

## Managing Sub-Projects

Each sub-project under `projects/` is completely independent:
- Separate virtual environment
- Own dependencies
- Isolated from other projects
- Can use different Python versions (with pyenv or similar)

## Development

Add your POC projects to the `projects/` directory. Check individual project READMEs for specific setup instructions.

---

For more information, see [Copilot Instructions](.github/copilot-instructions.md)
