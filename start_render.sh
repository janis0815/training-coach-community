#!/bin/bash
# Startet OAuth-Server im Hintergrund und Bot im Vordergrund
python oauth_server.py &
python bot.py
