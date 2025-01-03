# Release Checklist

Things we need to do for each release.

1. Increment `version` in [pyproject.toml](../pyproject.toml)
1. Update `poetry.lock` with: `poetry lock`
1. Update `requirements.txt` with: `poetry export --format=requirements.txt > requirements.txt`
1. Make sure all [development tools](../README.md#development) are happy
1. Run blackduck to generate a new NOTICE file: `bash <(curl -s -L https://detect.blackduck.com/detect10.sh) --blackduck.api.token='******')`
1. Create PR
1. After PR is merged, push a new tag
1. Create a new release from the tag.

