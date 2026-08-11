# Changelog

All notable changes to this project will be documented in this file.

### Diagram

- Use runtime activity names and add README/usage/DESIGN flow diagrams (#85) 

### ⚙️ Miscellaneous Tasks

- *(deps)* Bump ruff from 0.16.0 to 0.16.1 (#108) 
- *(codeql)* Bump codeql-action init+analyze to v4.37.6 together 
- *(deps)* Bump actions/stale from 10.4.0 to 11.0.0 (#105) 
- *(deps)* Bump ruff from 0.15.22 to 0.16.0 (#106) 
- Track issue priority via priority:* labels instead of body line (#107) 
- *(deps)* Bump github/codeql-action/analyze from 4.37.0 to 4.37.3 (#94) 
- *(deps)* Bump actions/setup-python from 6.3.0 to 7.0.0 (#96) 
- *(deps)* Bump actions/checkout from 7.0.0 to 7.0.1 (#95) 
- *(deps)* Bump ruff from 0.15.21 to 0.15.22 (#93) 
- *(deps)* Bump github/codeql-action/init from 4.37.0 to 4.37.3 (#92) 
- *(deps)* Bump github/codeql-action/analyze from 4.36.3 to 4.37.0 (#74) 
- *(deps)* Bump github/codeql-action/init from 4.36.3 to 4.37.0 (#72) 
- *(deps)* Bump actions/stale from 10.3.0 to 10.4.0 (#75) 
- *(deps)* Bump ruff from 0.15.20 to 0.15.21 (#76) 
- *(deps)* Bump mypy from 2.1.0 to 2.3.0 (#77) 
- Align AGENTS.md test_public_api guidance and enforce 95% coverage floor (#71) 
- Align all pre-rename URLs with canonical -python repository (#65) 
- *(deps)* Bump github/codeql-action init+analyze to v4.36.3 (#64) 
- *(deps)* Bump codecov/codecov-action from 6.0.1 to 7.0.0 (#41) 
- *(deps)* Bump actions/setup-python from 6.2.0 to 6.3.0 (#56) 
- *(deps)* Bump actions/checkout from 6.0.3 to 7.0.0 (#57) 
- *(deps)* Bump ruff from 0.15.15 to 0.15.20 (#61) 
- *(metadata)* Align project URLs with canonical -python repository (#44) 
- *(deps)* Bump github/codeql-action from 4.35.4 to 4.36.1 (#39) 
- *(deps)* Bump actions/checkout from 6.0.2 to 6.0.3 (#38) 
- *(deps)* Bump ruff from 0.15.12 to 0.15.15 (#37) 
- *(deps)* Bump actions/stale from 10.2.0 to 10.3.0 (#34) 
- *(deps)* Bump codecov/codecov-action from 6.0.0 to 6.0.1 (#31) 

### 🐛 Bug Fixes

- *(deps)* Pin azure-functions and azure-functions-durable (#117) 
- *(ci)* Correct stale workflow repo-slug check after rename (#63) 
- *(tests)* Migrate version test from hardcoded literal to importlib.metadata (#62) 

### 💼 Other

- Bump version to 0.2.0 

### 📚 Documentation

- Add Branch Hygiene section to AGENTS.md 
- *(release)* Require cookbook dogfood verification after publish 
- Record self-contained endpoint-metadata decision (#111) (#112) 
- Require translation sync in the same PR as English changes (Closes #103) (#104) 
- Add Downloads badge to badge row (#102) 
- Add blank line before Ecosystem heading (#100) 
- Correct azure-functions-db description in ecosystem table (#98) 
- Deepen README durable concepts and add durable-concepts/deployment docs (#84) 
- Add discoverability metadata (pepy badge + llms.txt) (#90) 
- Add 'For AI Coding Assistants' section pointing to llms.txt (#79) 
- *(contributing)* Document GitHub Actions SHA pinning policy (#69) 
- *(agents)* Standardize AGENTS.md with coverage floor, PR workflow, action pinning, and release process (#67) 
- *(release)* Document PyPI trusted publisher setup and troubleshooting (#40) 
- *(portal)* Add Azure Portal screenshots to quickstart and content classifier (#53) (#54) 

### 🚀 Features

- *(openapi)* Emit request/response schemas in build_openapi (#114) 

### 🚜 Refactor

- *(runtime)* Extract testable orchestrator/activities and derive OpenAPI from blueprint (#91) 
- *(runtime)* Harden error handling and registry observability (#88) 

### 🧪 Testing

- *(e2e)* Add replay, redeploy-hash, and event lifecycle scenarios (#118) 
- Add direct unit tests for registry and manifest core logic (#86) 

### ⚙️ Miscellaneous Tasks

- *(deps)* Bump mypy from 1.20.1 to 2.1.0 
- *(deps)* Bump ruff from 0.15.10 to 0.15.12 
- *(deps)* Bump github/codeql-action from 4.35.2 to 4.35.4 
- *(deps)* Bump actions/github-script from 8.0.0 to 9.0.0 
- *(deps)* Bump github/codeql-action from 4.35.1 to 4.35.2 
- *(deps)* Bump mypy from 1.20.0 to 1.20.1 
- *(deps)* Bump actions/upload-artifact from 7.0.0 to 7.0.1 
- Add tests/e2e/ directory and test-unit/test-e2e Makefile targets (#16) 
- Add llms.txt, llms-full.txt and bump ruff to 0.15.10 (#14) 

### 🐛 Bug Fixes

- *(test)* Add return type annotation to e2e_base_url fixture (#23) 

### 💼 Other

- Bump version to 0.1.1 

### 📚 Documentation

- Update changelog 
- Fix ecosystem table names, badges, and Part of intro line 
- Fix self-repo badge/codecov URLs and ecosystem row to use -python suffix 
- Mark cookbook as dogfood, fix ecosystem table description 
- Fix cross-repo links and README title 
- *(agents)* Add Issue Conventions section to AGENTS.md 

### ⚙️ Miscellaneous Tasks

- *(deps)* Bump codecov/codecov-action from 5.5.3 to 6.0.0 (#1) 
- *(deps)* Update pytest-asyncio requirement (#2) 
- *(deps)* Bump github/codeql-action from 4.33.0 to 4.35.1 (#3) 
- *(deps)* Bump anchore/sbom-action from 0.23.1 to 0.24.0 (#4) 
- *(deps)* Bump mypy from 1.19.1 to 1.20.0 (#6) 
- *(deps)* Bump ruff from 0.15.7 to 0.15.9 (#9) 
- Raise coverage fail_under threshold from 80% to 90% 

### 🐛 Bug Fixes

- Validate route targets at runtime, harden input/logging, clean ambiguous fields 
- Add RouteDecision validator, build-time edge checks, tests, and alpha disclaimer 
- Harden HTTP layer and pass graph_hash through orchestrator 
- Add graph_hash pinning, unify event contract, harden handler identity 

### 💼 Other

- Bump version to 0.1.0 

### 📚 Documentation

- Update changelog 
- Standardize ecosystem table in README 

### 🚀 Features

- Add standalone deployable examples with Oracle review fixes 
- Initial scaffold for azure-functions-langgraph 

### 🚜 Refactor

- Rename to azure-functions-durable-graph, fix Oracle review findings 

### 🧪 Testing

- Expand app.py coverage to 99% with HTTP handler, orchestrator, and activity tests 
<!-- generated by git-cliff -->
