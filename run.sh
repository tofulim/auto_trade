docker compose up airflow-init
sudo chown -R "${AIRFLOW_UID}:0" ./airflow
tmux kill-session -t "auto-trade" || true
tmux new -d -s "auto-trade" docker compose up --build
