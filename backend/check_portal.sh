#!/bin/bash
echo "🔄 Monitorando portal UERN..."
while true; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://portal.uern.br/prae/)
    if [ "$STATUS" = "200" ]; then
        echo "✅ Portal UERN está ONLINE! ($(date))"
        echo "Rodando scrapers..."
        cd ~/projetos/techhub
        source venv/bin/activate
        cd backend
        python scraper_prae.py
        python scraper_proex.py
        break
    else
        echo "⏳ Portal ainda offline (Status: $STATUS) - $(date)"
        sleep 60
    fi
done

## Se o portal cair de novo
##./check_portal.sh  # Vai verificar a cada 60 segundos