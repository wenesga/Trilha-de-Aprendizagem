#!/bin/sh
set -e
mkdir -p "$TRILHA_DIR_DADOS"
for f in conteudos.json config_sistema.json; do
  if [ ! -f "$TRILHA_DIR_DADOS/$f" ]; then
    cp "/app/seed/$f" "$TRILHA_DIR_DADOS/$f"
  fi
done
exec streamlit run trilha_aprendizagem.py \
  --server.port=8080 --server.address=0.0.0.0 \
  --server.headless=true --server.fileWatcherType=none \
  --server.runOnSave=false
