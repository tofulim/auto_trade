echo "AIRFLOW_UID=$(id -u)" > .env
echo "AIRFLOW_GID=$(id -g)" >> .env

mkdir airflow || true
mkdir shared || true


tmux kill-session -t "auto-trade" || true
tmux new -d -s "auto-trade" docker compose up --build
