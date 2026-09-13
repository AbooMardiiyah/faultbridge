# Railway Deployment

## Recommended Topology

Deploy FaultBridge as two services in one Railway project:

1. a PostgreSQL database created from Railway's PostgreSQL template;
2. the FaultBridge web/API service built from this repository's `Dockerfile`.

The browser UI and FastAPI API share one origin, and Railway supports the HTTP/1.1
WebSockets used by the voice endpoint. FaultBridge streams audio and does not need
a filesystem volume. Keep PostgreSQL private and reference its internal
`DATABASE_URL`; do not expose its TCP proxy for the demo.

## Deployment Steps

1. Push the repository to GitHub and create an empty Railway project.
2. Add **Database → PostgreSQL**.
3. Add a service from the GitHub repository. If this repository is inside a larger
   repository, set its root directory to `/faultbridge-intron`. Railway detects the
   root `Dockerfile` automatically.
4. Add `DATABASE_URL=${{Postgres.DATABASE_URL}}` as a reference variable.
5. Add these secret variables:

   ```text
   FAULTBRIDGE_PSEUDONYM_SECRET=<at least 32 random characters>
   FAULTBRIDGE_INTERNAL_API_KEY=<at least 32 random characters>
   SAHARA_API_KEY=<Sahara key>
   STT_PROVIDER=sahara
   TTS_PROVIDER=sahara
   AGENT_PROVIDER=together
   AGENT_MODEL=meta-llama/Llama-3.3-70B-Instruct-Turbo
   TOGETHER_API_KEY=<key>
   ```

   OpenAI and Groq remain supported alternatives. Add operator webhook variables
   only when delivery is enabled.
6. Set the health-check path to `/health/ready` and leave the injected `PORT`
   unchanged. The container applies idempotent SQL migrations before starting and
   binds Uvicorn to `0.0.0.0:${PORT}`.
7. Under **Networking**, generate a public Railway domain. Verify `/health/live`,
   `/health/ready`, `/`, and `/operations`, then complete a Sahara voice turn.

Both interfaces ask for the internal access key and keep it only in browser
`sessionStorage`. Enter it before recording the demo. If judges receive an
interactive URL, provide a temporary demo key through the private submission field
or judge instructions; never commit it to GitHub or embed it in frontend code.

Railway's current documentation confirms automatic Dockerfile detection,
PostgreSQL `DATABASE_URL` references over private networking, injected `PORT`,
deployment health checks, public TLS domains, and WebSocket support:

- <https://docs.railway.com/builds/dockerfiles>
- <https://docs.railway.com/databases/postgresql>
- <https://docs.railway.com/networking/public-networking/specs-and-limits>
- <https://docs.railway.com/deployments/healthchecks>

## Optional Worker

The API safely queues compensation and callback commands without a worker. For a
real connector demonstration, add a second service from the same repository,
override its start command to `uv run python3 scripts/run_worker.py`, reuse the
private `DATABASE_URL`, and configure the operator webhooks. Do not give the worker
a public domain.

## Demo Checks

- Use synthetic account and incident records only.
- Keep the internal API key out of browser code and the video.
- Confirm the domain works in an incognito window.
- Check browser microphone permission and HTTPS before recording.
- Run one complete rehearsal after deployment; do not discover API credit or
  language-parameter problems during the recorded demo.
