#!/bin/sh
# Manual deploy = same as auto-deploy but forced even if nothing changed.
/opt/basira/autodeploy.sh --force; tail -6 /var/log/basira-deploy.log
