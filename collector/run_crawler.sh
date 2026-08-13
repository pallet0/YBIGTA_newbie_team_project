#!/bin/bash
cd /home/ec2-user/ybigta-mcp/collector
docker run -d -p 4444:4444 --shm-size=512m --name selenium-temp selenium/standalone-chrome
sleep 10
python3 main.py >> /home/ec2-user/ybigta-mcp/collector/collector.log 2>&1
docker stop selenium-temp
docker rm -f selenium-temp
