#!/usr/bin/env bash
set -euo pipefail

# J.A.R.V.I.S. Trading System — Automated Code Review
# Usage: ./scripts/code-review.sh [--fix]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

issues=0
warnings=0

pass()    { printf "  \033[32m✓\033[0m %s\n" "$1"; }
fail()    { printf "  \033[31m✗\033[0m %s\n" "$1"; issues=$((issues + 1)); }
warn()    { printf "  \033[33m!\033[0m %s\n" "$1"; warnings=$((warnings + 1)); }

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     J.A.R.V.I.S. Code Review                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ========== 1. Python syntax check ==========
echo "[Python]"
if [[ -f "$PROJECT_DIR/server.py" ]]; then
    if python3 -m py_compile "$PROJECT_DIR/server.py" 2>/dev/null; then
        pass "server.py — syntax valid"
    else
        fail "server.py — syntax errors detected"
    fi
else
    fail "server.py — file not found"
fi

# Check for additional Python files
while IFS= read -r -d '' pyfile; do
    relpath="${pyfile#"$PROJECT_DIR/"}"
    if python3 -m py_compile "$pyfile" 2>/dev/null; then
        pass "$relpath — syntax valid"
    else
        fail "$relpath — syntax errors"
    fi
done < <(find "$PROJECT_DIR" -name "*.py" ! -name "server.py" ! -path "*/__pycache__/*" -print0 2>/dev/null)

# ========== 2. HTML structure check ==========
echo ""
echo "[HTML]"
if [[ -f "$PROJECT_DIR/dashboard.html" ]]; then
    html_content=$(cat "$PROJECT_DIR/dashboard.html")

    # Tag balance checks
    for tag in html head body style script; do
        open_count=$(grep -oi "<${tag}[> ]" <<< "$html_content" | wc -l)
        close_count=$(grep -oi "</${tag}>" <<< "$html_content" | wc -l)
        if [[ "$open_count" -eq "$close_count" ]]; then
            pass "<$tag> tags balanced ($open_count open, $close_count close)"
        else
            fail "<$tag> tags unbalanced ($open_count open, $close_count close)"
        fi
    done

    # Check for unclosed divs (approximate)
    div_open=$(grep -o '<div' <<< "$html_content" | wc -l)
    div_close=$(grep -o '</div>' <<< "$html_content" | wc -l)
    div_diff=$((div_open - div_close))
    if [[ "${div_diff#-}" -le 1 ]]; then
        pass "<div> tags approximately balanced ($div_open open, $div_close close)"
    else
        warn "<div> tag imbalance: $div_open open, $div_close close (diff: $div_diff)"
    fi
else
    fail "dashboard.html — file not found"
fi

# ========== 3. Security patterns ==========
echo ""
echo "[Security]"

# Dangerous Python patterns
if [[ -f "$PROJECT_DIR/server.py" ]]; then
    for pattern in "eval(" "exec(" "os.system(" "subprocess.call(" "__import__"; do
        if grep -qn "$pattern" "$PROJECT_DIR/server.py" 2>/dev/null; then
            count=$(grep -c "$pattern" "$PROJECT_DIR/server.py")
            warn "server.py contains '$pattern' ($count occurrence(s))"
        fi
    done

    # Hardcoded secrets
    if grep -qnE '(api_key|secret|password|token)\s*=\s*["\x27][A-Za-z0-9]{16,}' "$PROJECT_DIR/server.py" 2>/dev/null; then
        fail "server.py — possible hardcoded secret detected"
    else
        pass "server.py — no hardcoded secrets found"
    fi

    # SQL injection (raw string formatting in queries)
    raw_sql=$(grep -cnE 'execute\(.*%s|execute\(.*\.format\(' "$PROJECT_DIR/server.py" 2>/dev/null || echo "0")
    if [[ "$raw_sql" -gt 0 ]]; then
        warn "server.py — $raw_sql possible raw SQL formatting (check for injection)"
    else
        pass "server.py — SQL queries use parameterized style"
    fi
fi

# Check .env / secrets in repo
for sensitive in ".env" "secret.key" "credentials.json" ".aws"; do
    if [[ -f "$PROJECT_DIR/$sensitive" ]]; then
        if git -C "$PROJECT_DIR" ls-files --error-unmatch "$sensitive" >/dev/null 2>&1; then
            fail "$sensitive is tracked by git!"
        else
            pass "$sensitive exists but not tracked by git"
        fi
    fi
done

# ========== 4. Dependencies ==========
echo ""
echo "[Dependencies]"
if [[ -f "$PROJECT_DIR/requirements.txt" ]]; then
    req_count=$(wc -l < "$PROJECT_DIR/requirements.txt")
    pass "requirements.txt present ($req_count packages)"

    while IFS= read -r pkg; do
        pkg_name=$(echo "$pkg" | tr -d '[:space:]' | cut -d'=' -f1 | cut -d'>' -f1 | cut -d'<' -f1)
        [[ -z "$pkg_name" ]] && continue
        if python3 -c "import ${pkg_name//-/_}" 2>/dev/null; then
            pass "$pkg_name — installed"
        else
            warn "$pkg_name — not installed"
        fi
    done < "$PROJECT_DIR/requirements.txt"
else
    fail "requirements.txt — not found"
fi

# ========== 5. File structure ==========
echo ""
echo "[Structure]"
for f in server.py dashboard.html lw-charts.js requirements.txt; do
    if [[ -f "$PROJECT_DIR/$f" ]]; then
        size=$(wc -l < "$PROJECT_DIR/$f")
        pass "$f ($size lines)"
    else
        fail "$f — missing"
    fi
done

# Scripts
script_count=$(find "$PROJECT_DIR/scripts" -name "*.sh" -type f 2>/dev/null | wc -l)
pass "scripts/ — $script_count shell scripts"

# ========== 6. Git status ==========
echo ""
echo "[Git]"
if git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    branch=$(git -C "$PROJECT_DIR" branch --show-current)
    pass "Branch: $branch"

    uncommitted=$(git -C "$PROJECT_DIR" status --porcelain | wc -l)
    if [[ "$uncommitted" -eq 0 ]]; then
        pass "Working tree clean"
    else
        warn "$uncommitted uncommitted change(s)"
    fi

    if [[ -f "$PROJECT_DIR/.gitignore" ]]; then
        pass ".gitignore present"
    else
        warn ".gitignore missing"
    fi
else
    warn "Not a git repository"
fi

# ========== Summary ==========
echo ""
echo "──────────────────────────────────────────────"
printf "Issues: \033[31m%d\033[0m | Warnings: \033[33m%d\033[0m\n" "$issues" "$warnings"
echo ""

if [[ $issues -eq 0 && $warnings -eq 0 ]]; then
    echo "All clear — code review passed."
elif [[ $issues -eq 0 ]]; then
    echo "No blockers — $warnings warning(s) to review."
else
    echo "$issues issue(s) found — review required."
    exit 1
fi
