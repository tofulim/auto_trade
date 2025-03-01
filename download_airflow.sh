#! /bin/bash

AIRFLOW_VERSION=2.7.1
export AIRFLOW_HOME=$(pwd)/airflow
# Extract the version of Python you have installed. If you're currently using a Python version that is not supported by Airflow, you may want to set this manually.
# See above for supported versions.

PYTHON_VERSION="$(python3 --version | cut -d " " -f 2 | cut -d "." -f 1-2)"
echo "Python version: ${PYTHON_VERSION}"
CONSTRAINT_URL="https://raw.githubusercontent.com/apache/airflow/constraints-${AIRFLOW_VERSION}/constraints-${PYTHON_VERSION}.txt"

echo $CONSTRAINT_URL
# For example this would install 2.8.3 with python 3.8: https://raw.githubusercontent.com/apache/airflow/constraints-2.8.3/constraints-3.8.txt
pip install "apache-airflow==${AIRFLOW_VERSION}" --constraint "${CONSTRAINT_URL}"
