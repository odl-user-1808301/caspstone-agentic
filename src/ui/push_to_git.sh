#!/bin/bash
set -e

FILE="$1"

git add "$FILE"
git commit -m "Atualiza $FILE automaticamente"
git push