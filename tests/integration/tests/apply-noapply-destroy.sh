#!/bin/bash

terraform init
terraform apply -auto-approve
out=$(terraform apply -no-color -auto-approve)
echo $out
target="No changes. Your infrastructure matches the configuration."
if ! [[ "$out" == *"$target"* ]]; then
  exit 1
fi
terraform destroy -auto-approve

