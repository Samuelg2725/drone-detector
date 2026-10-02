# ~/.bashrc for dev container

# Aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git pull'
alias gd='git diff'
alias glog='git log --oneline --graph'

# Docker aliases
alias d='docker'
alias dc='docker-compose'
alias dps='docker ps'
alias di='docker images'
alias dexec='docker exec -it'

# Python aliases
alias python=python3
alias pip=pip3
alias pytest='pytest -v'

# Drone Detector aliases
alias run-api='python run.py --mock'
alias run-tests='pytest tests/ -v'
alias run-coverage='pytest --cov=app --cov-report=html'
alias train-model='python scripts/train_model.py'

# Prompt
PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

# Path
export PATH="$PATH:$HOME/.local/bin"

# Python path
export PYTHONPATH="/workspace:$PYTHONPATH"

# Environment
export ENVIRONMENT="development"
export LOG_LEVEL="DEBUG"
export USE_MOCK_HARDWARE="true"