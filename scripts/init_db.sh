#!/bin/bash
set -e
sudo -u postgres psql -c "CREATE DATABASE printcode_guard;" 2>/dev/null || echo "Database may already exist"
sudo -u postgres psql -d printcode_guard -c "GRANT ALL ON SCHEMA public TO $(whoami);"
sudo -u postgres psql -d printcode_guard -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $(whoami);"
sudo -u postgres psql -d printcode_guard -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $(whoami);"
