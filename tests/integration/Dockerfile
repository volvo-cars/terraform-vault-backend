# Stage 1: Retrieve binaries from source_image
FROM hashicorp/vault:1.16.2 AS vault

RUN which vault

FROM hashicorp/terraform:latest
COPY --from=vault /bin/vault /bin

WORKDIR /app
RUN apk add --no-cache bash
RUN apk --no-cache add jq

ARG TEST_FILE

COPY main.tf.* /app
COPY entrypoint.sh /app
COPY tests /app/tests

# Set the entrypoint script
ENTRYPOINT ["/app/entrypoint.sh"]
