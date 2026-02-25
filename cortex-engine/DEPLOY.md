# Deploying CortexOS to Railway

## Prerequisites
- Railway account
- GitHub repo (private) with cortex-engine code
- PostgreSQL plugin on Railway

## Steps
1. Create Railway project
2. Add PostgreSQL plugin, enable pgvector extension
3. Connect GitHub repo (private)
4. Set env vars: DATABASE_URL (auto), CORTEX_ADMIN_SECRET,
   OPENAI_API_KEY, CORTEX_LLM_PROVIDER
5. Deploy — Railway builds from Dockerfile
6. Set custom domain: api.cortexos.dev
7. Test: curl https://api.cortexos.dev/healthz
8. Create first API key via admin endpoint
