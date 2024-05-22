AIRFLOW_VERSION=2.7.0
export AIRFLOW_HOME=./airflow
# Extract the version of Python you have installed. If you're currently using a Python version that is not supported by Airflow, you may want to set this manually.
# See above for supported versions.

PYTHON_VERSION="$(python --version | cut -d " " -f 2 | cut -d "." -f 1-2)"
echo "Python version: ${PYTHON_VERSION}"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

# For example this would install 2.8.3 with python 3.8: https://raw.githubusercontent.com/apache/airflow/constraints-2.8.3/constraints-3.8.txt
# aws ec2에서 진행하면 반드시 sudo를 붙이는 게 좋다.
# 그렇지 않으면 airflow home dir이 ./bin 이하로 가버린다.
sudo pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
