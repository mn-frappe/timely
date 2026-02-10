#!/bin/bash
set -e

cd ~ || exit

sudo apt update
sudo apt remove mysql-server mysql-client || true
sudo apt install -y libcups2-dev redis-server mariadb-client libmariadb-dev

pip install frappe-bench

# Use the same branch as the PR target or current branch
githubbranch=${GITHUB_BASE_REF:-${GITHUB_REF##*/}}
frappebranch=${githubbranch}
erpnextbranch=${githubbranch}
hrmsbranch=${githubbranch}

# Clone frappe from the correct branch
git clone "https://github.com/frappe/frappe" --branch "${frappebranch}" --depth 1
bench init --skip-assets --frappe-path ~/frappe --python "$(which python)" frappe-bench

mkdir ~/frappe-bench/sites/test_site
cp -r "${GITHUB_WORKSPACE}/.github/helper/site_config.json" ~/frappe-bench/sites/test_site/

# Setup MariaDB
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL character_set_server = 'utf8mb4'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "SET GLOBAL collation_server = 'utf8mb4_unicode_ci'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE USER 'test_frappe'@'localhost' IDENTIFIED BY 'test_frappe'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "CREATE DATABASE test_frappe"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "GRANT ALL PRIVILEGES ON \`test_frappe\`.* TO 'test_frappe'@'localhost'"
mariadb --host 127.0.0.1 --port 3306 -u root -proot -e "FLUSH PRIVILEGES"

cd ~/frappe-bench || exit

# Disable unnecessary Procfile entries
sed -i 's/watch:/# watch:/g' Procfile
sed -i 's/schedule:/# schedule:/g' Procfile
sed -i 's/socketio:/# socketio:/g' Procfile
sed -i 's/redis_socketio:/# redis_socketio:/g' Procfile

# Install dependencies
bench get-app erpnext --branch "${erpnextbranch}" --resolve-deps
bench get-app hrms --branch "${hrmsbranch}"
bench get-app timely "${GITHUB_WORKSPACE}"
bench setup requirements --dev

# Build and setup site
bench start &>> ~/frappe-bench/bench_start.log &
CI=Yes bench build --app frappe &
bench --site test_site reinstall --yes

bench --verbose --site test_site install-app timely
