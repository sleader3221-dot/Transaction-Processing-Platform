#!/bin/bash
# Comprehensive Submission Verification Script

echo "═══════════════════════════════════════════════════════════"
echo "📋 TRANSACTION PLATFORM - SUBMISSION VERIFICATION"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

# Helper functions
check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    ((FAIL++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

echo "1️⃣  CHECKING DOCUMENTATION FILES..."
echo ""

[[ -f "README.md" ]] && check_pass "README.md exists" || check_fail "README.md missing"
[[ -f "ARCHITECTURE.md" ]] && check_pass "ARCHITECTURE.md exists" || check_fail "ARCHITECTURE.md missing"
[[ -f "AZURE_DEPLOYMENT.md" ]] && check_pass "AZURE_DEPLOYMENT.md exists" || check_fail "AZURE_DEPLOYMENT.md missing"
[[ -f "REQUIREMENTS_VERIFICATION.md" ]] && check_pass "REQUIREMENTS_VERIFICATION.md exists" || check_fail "REQUIREMENTS_VERIFICATION.md missing"
[[ -f "FINAL_SUBMISSION_SUMMARY.md" ]] && check_pass "FINAL_SUBMISSION_SUMMARY.md exists" || check_fail "FINAL_SUBMISSION_SUMMARY.md missing"
[[ -f "INDEX.md" ]] && check_pass "INDEX.md exists" || check_fail "INDEX.md missing"
[[ -f "NEXT_STEPS.md" ]] && check_pass "NEXT_STEPS.md exists" || check_fail "NEXT_STEPS.md missing"

echo ""
echo "2️⃣  CHECKING APPLICATION CODE..."
echo ""

[[ -f "app/main.py" ]] && check_pass "app/main.py exists" || check_fail "app/main.py missing"
[[ -f "app/config.py" ]] && check_pass "app/config.py exists" || check_fail "app/config.py missing"
[[ -f "app/api/health.py" ]] && check_pass "app/api/health.py exists" || check_fail "app/api/health.py missing"
[[ -f "app/api/v1/imports.py" ]] && check_pass "app/api/v1/imports.py exists" || check_fail "app/api/v1/imports.py missing"
[[ -f "app/api/v1/transactions.py" ]] && check_pass "app/api/v1/transactions.py exists" || check_fail "app/api/v1/transactions.py missing"
[[ -f "app/api/v1/accounts.py" ]] && check_pass "app/api/v1/accounts.py exists" || check_fail "app/api/v1/accounts.py missing"
[[ -f "app/workers/import_worker.py" ]] && check_pass "app/workers/import_worker.py exists" || check_fail "app/workers/import_worker.py missing"
[[ -f "app/redis_client/cache.py" ]] && check_pass "app/redis_client/cache.py exists" || check_fail "app/redis_client/cache.py missing"
[[ -f "app/redis_client/rate_limiter.py" ]] && check_pass "app/redis_client/rate_limiter.py exists" || check_fail "app/redis_client/rate_limiter.py missing"
[[ -f "app/core/auth.py" ]] && check_pass "app/core/auth.py exists" || check_fail "app/core/auth.py missing"
[[ -f "app/core/validation.py" ]] && check_pass "app/core/validation.py exists" || check_fail "app/core/validation.py missing"

echo ""
echo "3️⃣  CHECKING DATABASE & MIGRATIONS..."
echo ""

[[ -f "migrations/alembic.ini" ]] && check_pass "migrations/alembic.ini exists" || check_fail "migrations/alembic.ini missing"
[[ -f "migrations/env.py" ]] && check_pass "migrations/env.py exists" || check_fail "migrations/env.py missing"
[[ -f "migrations/versions/001_initial.py" ]] && check_pass "migrations/001_initial.py exists" || check_fail "migrations/001_initial.py missing"

echo ""
echo "4️⃣  CHECKING CONFIGURATION & ENVIRONMENT..."
echo ""

[[ -f "Dockerfile" ]] && check_pass "Dockerfile exists" || check_fail "Dockerfile missing"
[[ -f "docker-compose.yml" ]] && check_pass "docker-compose.yml exists" || check_fail "docker-compose.yml missing"
[[ -f ".env.example" ]] && check_pass ".env.example exists" || check_fail ".env.example missing"
[[ -f ".gitignore" ]] && check_pass ".gitignore exists" || check_fail ".gitignore missing"
[[ -f "requirements.txt" ]] && check_pass "requirements.txt exists" || check_fail "requirements.txt missing"

echo ""
echo "5️⃣  CHECKING TEST SUITE..."
echo ""

[[ -d "tests/unit" ]] && check_pass "tests/unit/ exists" || check_fail "tests/unit/ missing"
[[ -d "tests/api" ]] && check_pass "tests/api/ exists" || check_fail "tests/api/ missing"
[[ -d "tests/integration" ]] && check_pass "tests/integration/ exists" || check_fail "tests/integration/ missing"
[[ -d "tests/concurrency" ]] && check_pass "tests/concurrency/ exists" || check_fail "tests/concurrency/ missing"
[[ -d "tests/failure" ]] && check_pass "tests/failure/ exists" || check_fail "tests/failure/ missing"
[[ -f "tests/conftest.py" ]] && check_pass "tests/conftest.py exists" || check_fail "tests/conftest.py missing"

echo ""
echo "6️⃣  CHECKING SCRIPTS & UTILITIES..."
echo ""

[[ -f "scripts/create_api_key.py" ]] && check_pass "scripts/create_api_key.py exists" || check_fail "scripts/create_api_key.py missing"
[[ -f "scripts/generate_test_csv.py" ]] && check_pass "scripts/generate_test_csv.py exists" || check_fail "scripts/generate_test_csv.py missing"

echo ""
echo "7️⃣  CHECKING DEPLOYMENT..."
echo ""

[[ -f "deployment/deploy.sh" ]] && check_pass "deployment/deploy.sh exists" || check_fail "deployment/deploy.sh missing"
[[ -f "deployment/container-app.bicep" ]] && check_pass "deployment/container-app.bicep exists" || check_fail "deployment/container-app.bicep missing"

echo ""
echo "8️⃣  CHECKING PERFORMANCE TESTING..."
echo ""

[[ -f "load_test/locustfile.py" ]] && check_pass "load_test/locustfile.py exists" || check_fail "load_test/locustfile.py missing"
[[ -f "load_test/results.md" ]] && check_pass "load_test/results.md exists" || check_fail "load_test/results.md missing"

echo ""
echo "9️⃣  CHECKING FOR SECRETS..."
echo ""

# Check if .env file exists (should not in git)
if grep -q ".env" .gitignore 2>/dev/null; then
    check_pass ".env is in .gitignore"
else
    check_warn ".env might not be in .gitignore"
fi

# Check for hardcoded secrets
SECRET_COUNT=$(grep -r "password.*=" app/ scripts/ --include="*.py" 2>/dev/null | grep -v "password_reset" | grep -v "PASSWORD" | grep -v "#" | wc -l)
if [ "$SECRET_COUNT" -eq 0 ]; then
    check_pass "No hardcoded passwords found"
else
    check_fail "Found potential hardcoded secrets"
fi

echo ""
echo "🔟 CHECKING GIT REPOSITORY..."
echo ""

if [ -d ".git" ]; then
    check_pass "Git repository initialized"
    
    REMOTE=$(git remote -v 2>/dev/null | wc -l)
    if [ "$REMOTE" -gt 0 ]; then
        check_pass "Git remote configured"
    else
        check_warn "Git remote not configured yet"
    fi
    
    COMMITS=$(git rev-list --count HEAD 2>/dev/null)
    if [ "$COMMITS" -gt 0 ]; then
        check_pass "Git commits exist ($COMMITS commits)"
    else
        check_fail "No commits found"
    fi
else
    check_warn "Git repository not initialized yet"
fi

echo ""
echo "1️⃣1️⃣  CHECKING DOCKER SETUP..."
echo ""

if command -v docker &> /dev/null; then
    check_pass "Docker is installed"
else
    check_warn "Docker not found in PATH"
fi

if command -v docker-compose &> /dev/null || docker compose --version &>/dev/null; then
    check_pass "Docker Compose is available"
else
    check_warn "Docker Compose not found"
fi

echo ""
echo "1️⃣2️⃣  CHECKING PYTHON DEPENDENCIES..."
echo ""

if [ -f "requirements.txt" ]; then
    if grep -q "fastapi" requirements.txt; then
        check_pass "FastAPI in requirements.txt"
    else
        check_fail "FastAPI not in requirements.txt"
    fi
    
    if grep -q "sqlalchemy" requirements.txt; then
        check_pass "SQLAlchemy in requirements.txt"
    else
        check_fail "SQLAlchemy not in requirements.txt"
    fi
    
    if grep -q "redis" requirements.txt; then
        check_pass "Redis in requirements.txt"
    else
        check_fail "Redis not in requirements.txt"
    fi
else
    check_fail "requirements.txt not found"
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "📊 VERIFICATION SUMMARY"
echo "═══════════════════════════════════════════════════════════"
echo ""

TOTAL=$((PASS + FAIL))
PERCENT=$((PASS * 100 / TOTAL))

echo -e "Passed:  ${GREEN}$PASS${NC}"
echo -e "Failed:  ${RED}$FAIL${NC}"
echo "Total:   $TOTAL"
echo ""
echo -e "Score:   ${GREEN}$PERCENT%${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "🎉 ALL CHECKS PASSED! Ready for submission."
    exit 0
else
    echo "⚠️  Some checks failed. Review above and fix before submission."
    exit 1
fi
