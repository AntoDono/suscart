#!/bin/bash
mkdir -p ./data
cd ./data
curl -L -o ./fresh-and-stale-classification.zip\
  https://www.kaggle.com/api/v1/datasets/download/swoyam2609/fresh-and-stale-classification