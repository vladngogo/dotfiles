# Global agent instructions

Applies in every repo. A repo's own `AGENTS.md` overrides anything here.
This file is machine-local: edit it freely — installs never overwrite it.

- Check facts about this machine (hardware, distro, versions) with a command
  before relying on them.
- Verify before claiming done: run the repo's tests/linters on what you
  changed and report failures as they are.
- Never commit secrets, credentials, or machine-specific paths.
