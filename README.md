# Self-Healing Data Pipeline Agent
This agent is capable of detecting failures at pipeline level and then fixing these failure using the given set of tools
all while being in the given set of guard rails given in the scope of the project.

All the detections and fixing actions performed by the agent will be saved in the postregsql database. 

## MVP Scope
The aim is to build a MVP (minimum viable product). This MVP is designed in such a way that it can be later on 
transfered to AWS setup make it working for a production pipeline. 
* Detect
* Diagnose
* Act
* Verify
* Learn

## Architecture (Local)
* Docker
* FastAPI
* Postgres
* MinIO
* Spark (local)
* Prometheus + Grafana

## Quick Start
TBD
