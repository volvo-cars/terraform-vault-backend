#!/bin/bash
terraform init

terraform apply -auto-approve
sed -i 's/STRING/APPENDEDSTRING/g' "main.tf"
out=$(terraform apply -no-color -auto-approve)
echo $out
target="must be replaced"
if ! [[ "$out" == *"$target"* ]]; then
  exit 1
fi
terraform destroy -auto-approve

