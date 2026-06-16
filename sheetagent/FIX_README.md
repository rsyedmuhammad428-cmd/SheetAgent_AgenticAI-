# SheetAgent AI — nginx "host not found" Fix

## What was wrong

Error:
  host not found in upstream "backend:8000"

Two causes:

1. nginx started BEFORE backend was ready
   nginx tries to resolve "backend:8000" at startup.
   If backend container isn't running yet, DNS lookup fails → nginx crashes.

2. nginx used static upstream blocks
   Static upstream{} blocks are resolved ONCE at startup.
   If backend isn't up yet, resolution fails permanently.

## The Fix

FIX 1 — nginx.conf: Use Docker's internal DNS resolver + set $variable
  resolver 127.0.0.11 valid=10s;   ← Docker's built-in DNS
  set $backend_upstream http://backend:8000;  ← runtime variable, not static
  proxy_pass $backend_upstream;    ← resolved at request time, not startup

  This means nginx can start even if backend isn't ready yet,
  and retries DNS on every request.

FIX 2 — docker-compose.yml: nginx depends_on backend with health check
  nginx:
    depends_on:
      backend:
        condition: service_healthy   ← wait for /health to return 200

  This makes nginx wait until backend is actually running before starting.

## Files to REPLACE — only 2 files

  nginx/nginx.conf       ← resolver + set $variable fix
  docker-compose.yml     ← depends_on with service_healthy

## PowerShell commands

  cd "D:\Data Entery AI_Agent\sheetagent"

  # Full restart in correct order (postgres → redis → backend → frontend → nginx)
  docker-compose down
  docker-compose up -d

  # Watch startup sequence
  docker-compose logs -f

  # Once backend shows "Application startup complete", nginx will start
  # Then open: http://localhost

## Expected healthy startup order

  1. postgres starts    → healthy
  2. redis starts       → healthy
  3. backend starts     → waits for postgres+redis → healthy (60s)
  4. frontend starts    → ready
  5. nginx starts last  → can now resolve backend:8000 → serves on port 80

## Verify

  curl http://localhost/health
  # {"status":"ok","version":"5.0.0"}

  curl http://localhost/
  # Returns HTML of React app
