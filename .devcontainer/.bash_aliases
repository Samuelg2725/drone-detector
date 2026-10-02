# Custom aliases for drone detector development

# Quick commands
alias dev-start='docker-compose -f docker-compose.dev.yml up -d'
alias dev-stop='docker-compose -f docker-compose.dev.yml down'
alias dev-logs='docker-compose -f docker-compose.dev.yml logs -f'
alias dev-shell='docker exec -it drone-app-dev bash'

# Testing
alias test-unit='pytest tests/unit/ -v'
alias test-int='pytest tests/integration/ -v'
alias test-perf='pytest tests/performance/ -v'
alias test-all='pytest tests/ -v'

# Database
alias db-migrate='python scripts/migrate.py upgrade head'
alias db-shell='psql -U drone_user -d drone_detector'
alias db-backup='python scripts/backup_database.py'

# Hardware
alias hackrf-info='hackrf_info'
alias rtl-test='rtl_test -t'
alias hackrf-sweep='hackrf_sweep -f 2400:2500'

# Signal processing
alias analyze-iq='python scripts/analyze_iq.py'
alias replay-iq='python scripts/replay_iq.py'