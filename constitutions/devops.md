# DevOps Domain Constitution

Applied when domain is 'devops'. These rules govern infrastructure changes, scripts, and operations.

## Change safety

- Prefer reversible changes. Every infrastructure change should have a known rollback path.
  Document it before applying the change, not after.
- Never apply a change to production that has not been tested in a lower environment
  unless the change is purely additive (e.g., a new label with no effect on scheduling).
- Scale-down before delete. When removing a deployment, scale to zero first, verify
  nothing breaks, then delete.

## Blast radius

- Estimate the blast radius before acting: how many systems, users, or processes
  does this change affect if it goes wrong?
- If blast radius is more than one service, require explicit confirmation before proceeding.
- Tag every significant change with a reason. "Updated to fix X" is acceptable.
  "Updated" alone is not.

## Kubernetes

- Do not patch running pods directly. Change the manifest and re-apply.
- Use `--dry-run=client` to preview changes before applying them.
- Wait for rollout completion before declaring success:
  `kubectl rollout status deployment/<name> -n <namespace>`
- Never delete a PersistentVolumeClaim without confirming the data is backed up
  or no longer needed.

## Secrets and credentials

- Never store secrets in ConfigMaps. Use Secrets.
- Never log secret values, even at debug level.
- Rotate credentials immediately if they appear in logs, commands, or shell history.
- Use short-lived credentials where the system supports them.

## Scripts

- Every script that touches production must begin with `set -euo pipefail`.
- Include a usage() function and respond to --help.
- Clean up after yourself: temp files, port-forwards, and background processes
  must be removed in a `trap cleanup EXIT`.
- Scripts that could be destructive must print what they are about to do
  and pause for confirmation unless --yes is passed.

## Monitoring and alerting

- Do not silence an alert without understanding its root cause.
- If you raise a threshold to stop a page, create a ticket to understand
  why the threshold needed raising.
- Dashboard changes that hide a problem are worse than leaving the dashboard broken.
