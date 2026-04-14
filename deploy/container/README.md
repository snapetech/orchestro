# Container Example

This is a minimal container recipe for running the Orchestro API.

Build:

```bash
docker build -f deploy/container/Dockerfile -t orchestro:local .
```

Run:

```bash
docker run --rm -p 8765:8765 -v "$PWD/.orchestro:/data" orchestro:local
```

Notes:

- this is a basic example, not a hardened production image
- mount persistent Orchestro state into `/data`
- if you rely on project-local instructions or constitutions, you will need to mount the repo or bake those files into the image

See also:

- [Deployment](../../docs/deployment.md)
- [API Operations](../../docs/api-operations.md)
