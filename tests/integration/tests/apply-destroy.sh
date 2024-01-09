#!/bin/bash

echo "hellooo $TF_HTTP_PASSWORD"

terraform init
terraform apply -auto-approve
test -f test.txt
terraform destroy -auto-approve
! test -f "test.txt"
