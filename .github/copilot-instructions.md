# Copilot Instructions for mypoc Monorepo

This is a Python monorepo workspace for proof of concept (POC) projects.

## Project Structure

- `app/` - Directory for sub-projects (each sub-project is independent)
- `docs/` - Project documentation
- `.vscode/` - VS Code workspace configuration

## How to Use This Monorepo

1. Create a new sub-project directory under `app/`
2. Each sub-project can have its own:
   - Virtual environment
   - `requirements.txt` or `pyproject.toml`
   - README with project-specific documentation
   - Main code files

## Example Sub-Project Structure

```
app/
  ├── project-1/
  │   ├── README.md
  │   ├── requirements.txt
  │   ├── src/
  │   └── tests/
  └── project-2/
      ├── README.md
      ├── requirements.txt
      ├── src/
      └── tests/
```

## Next Steps

- Create sub-projects within the `app/` directory
- Each project is independent and self-contained
- Use Python virtual environments for isolation
