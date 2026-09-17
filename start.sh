#!/bin/sh
gunicorn bot:app --bind 0.0.0.0:$PORT
