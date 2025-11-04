#!/bin/bash
# OAuth CTF Advanced - Monitoring Script

while true; do
  clear
  echo "============================================"
  echo "  OAuth CTF Advanced - Monitor"
  echo "  Time: $(date '+%Y-%m-%d %H:%M:%S')"
  echo "============================================"
  echo ""

  echo "📊 System Resources:"
  echo "-------------------------------------------"
  CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
  RAM=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100}')
  DISK=$(df -h / | awk 'NR==2 {print $5}' | cut -d'%' -f1)

  echo "  CPU:  ${CPU}%"
  echo "  RAM:  ${RAM}%"
  echo "  Disk: ${DISK}%"
  echo ""

  echo "🐳 Docker Status:"
  echo "-------------------------------------------"
  docker-compose ps
  echo ""

  echo "🌐 Active Connections:"
  echo "-------------------------------------------"
  CONNECTIONS=$(docker exec oauth-ctf-nginx netstat -an 2>/dev/null | grep :80 | grep ESTABLISHED | wc -l)
  echo "  HTTP: $CONNECTIONS connections"
  echo ""

  echo "📝 Recent Logs (last 30s):"
  echo "-------------------------------------------"
  docker-compose logs --tail=5 --since=30s 2>&1 | tail -10
  echo ""

  echo "⚠️  Alerts:"
  echo "-------------------------------------------"
  if (( $(echo "$CPU > 80" | bc -l) )); then
    echo "  🔴 HIGH CPU: ${CPU}%"
  fi
  if (( $(echo "$RAM > 85" | bc -l) )); then
    echo "  🔴 HIGH RAM: ${RAM}%"
  fi
  if (( $DISK > 80 )); then
    echo "  🔴 HIGH DISK: ${DISK}%"
  fi
  if [ $CONNECTIONS -gt 100 ]; then
    echo "  🟡 HIGH TRAFFIC: $CONNECTIONS connections"
  fi

  # Check if all containers are running
  RUNNING=$(docker-compose ps | grep "Up" | wc -l)
  if [ $RUNNING -lt 4 ]; then
    echo "  🔴 CONTAINERS DOWN: Only $RUNNING/4 running"
  fi

  echo ""
  echo "Press Ctrl+C to exit | Refreshing in 5s..."

  sleep 5
done
