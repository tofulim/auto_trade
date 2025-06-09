echo "AIRFLOW_UID=$(id -u)" > .env
echo "AIRFLOW_GID=$(id -g)" >> .env
# build한 docker image 버젼을 저장
echo "VERSION=${1}" >> .env

mkdir airflow || true
mkdir shared || true


tmux kill-session -t "auto-trade" || true
sleep 5  # 강제 대기
tmux new -d -s "auto-trade" docker compose up --build
