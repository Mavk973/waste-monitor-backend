# Script: start waste_monitor_backend
# Run from: waste_monitor_backend folder

$PG_PASSWORD = "qwerty"
$PG_USER     = "postgres"
$PG_HOST     = "localhost"
$PG_PORT     = "5432"
$DB_NAME     = "waste_monitor"

$env:PGPASSWORD = $PG_PASSWORD
$psql = "C:\Program Files\PostgreSQL\18\bin\psql.exe"

# 1. Create database if not exists
Write-Host "Creating database..." -ForegroundColor Cyan
& $psql -U $PG_USER -h $PG_HOST -p $PG_PORT -c "CREATE DATABASE $DB_NAME;" 2>&1 | Out-Null
Write-Host "OK" -ForegroundColor Green

# 2. Write DATABASE_URL to .env (no BOM - required for python-dotenv)
$envContent = "DATABASE_URL=postgresql://${PG_USER}:${PG_PASSWORD}@${PG_HOST}:${PG_PORT}/${DB_NAME}`nSECRET_KEY=supersecretkey1234567890abcdef1234567890abcdef`nALGORITHM=HS256`nACCESS_TOKEN_EXPIRE_MINUTES=1440"
[System.IO.File]::WriteAllText((Resolve-Path ".env").Path, $envContent, [System.Text.UTF8Encoding]::new($false))
Write-Host ".env updated" -ForegroundColor Green

# 3. Kill old uvicorn processes on port 8080
$oldProcs = netstat -ano | Select-String ":8080" | ForEach-Object { ($_ -split '\s+')[-1] } | Where-Object { $_ -match '^\d+$' } | Select-Object -Unique
foreach ($p in $oldProcs) {
    Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
}

# 4. Start server (tables created automatically)
Write-Host ""
Write-Host "Starting FastAPI server at http://localhost:8080 ..." -ForegroundColor Cyan
Write-Host "API docs: http://localhost:8080/docs" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""
python -m uvicorn main:app --host 0.0.0.0 --port 8080 --reload