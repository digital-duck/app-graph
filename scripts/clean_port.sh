#!/usr/bin/env bash
# Kill whatever process is listening on the given port(s).
# Usage: clean_port.sh <port1> [port2 ...]

set -u

if [ "$#" -eq 0 ]; then
    echo "Usage: $0 <port1> [port2 ...]" >&2
    exit 1
fi

for port in "$@"; do
    pids=$(lsof -t -i ":${port}" 2>/dev/null)
    if [ -z "$pids" ]; then
        echo "Port ${port}: nothing listening"
        continue
    fi
    for pid in $pids; do
        echo "Port ${port}: killing PID ${pid}"
        kill "$pid" 2>/dev/null
    done
done

sleep 1

for port in "$@"; do
    pids=$(lsof -t -i ":${port}" 2>/dev/null)
    for pid in $pids; do
        echo "Port ${port}: PID ${pid} still alive, sending SIGKILL"
        kill -9 "$pid" 2>/dev/null
    done
done
