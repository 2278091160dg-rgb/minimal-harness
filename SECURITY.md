# Security Policy

## Supported versions

Minimal Harness is currently pre-1.0. Security fixes are made on the latest release and the `main` branch. Older snapshots are not maintained separately.

## Reporting a vulnerability

Use GitHub private vulnerability reporting when it is available in the repository Security tab. If that option is not visible, contact the maintainer through the repository owner's GitHub profile before sharing exploit details.

Do not include secrets, private repository contents, personal data, or working exploit details in a public issue.

Please include:

- the affected commit or release;
- operating system, Python version, and Git version;
- a minimal reproduction using synthetic data;
- the security boundary that was crossed;
- whether evidence, Git scope, filesystem paths, or command execution is affected.

## Security boundary

Minimal Harness validates local task state, Git scope, evidence metadata, and completion gates. It is not:

- an operating-system sandbox;
- an authorization system for shell or network access;
- a cryptographic signature service;
- proof that a human manual attestation is truthful;
- protection against a process that already has unrestricted access to rewrite the repository and all Harness state.

Run untrusted code in an appropriate container, virtual machine, or restricted account. Review all task commands before execution.
