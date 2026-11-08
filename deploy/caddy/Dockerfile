# Same Caddy release, rebuilt with security-patched Go/modules. Not an official binary.
FROM golang:1.26.10-alpine@sha256:a2012b4a1d1f9f7e9f44e0d39b805a901e856b1dd80b4e6ee4338db547050308 AS build
ENV GOTOOLCHAIN=local CGO_ENABLED=0
RUN go mod download -json github.com/caddyserver/caddy/v2@v2.11.7 > /module.json \
    && cp -a /go/pkg/mod/github.com/caddyserver/caddy/v2@v2.11.7 /src \
    && chmod -R u+w /src
WORKDIR /src
RUN go get golang.org/x/net@v0.62.0 github.com/go-jose/go-jose/v4@v4.1.6 github.com/klauspost/compress@v1.20.2 \
    && go mod verify \
    && go list -m all > /modules.txt
RUN go build -trimpath -buildvcs=false -ldflags '-s -w -X github.com/caddyserver/caddy/v2.CustomVersion=v2.11.7-phase4e' -o /caddy ./cmd/caddy

FROM alpine:3.23@sha256:469c9ea410b9215eaee7976ba6c0639039b444be8e5d638f7abbada189971eb2
# Fresh runtime: no obsolete Caddy executable/curl in inherited image layers.
RUN apk add --no-cache ca-certificates=20261020-r0 tzdata=2026f-r0 zlib=1.4-r0 \
    mailcap=2.1.54-r0 openssl=3.5.9-r0 ssl_client=1.37.0-r30 \
    && mkdir -p /etc/caddy /config/caddy /data/caddy /srv
ENV XDG_CONFIG_HOME=/config XDG_DATA_HOME=/data
COPY --from=build /caddy /usr/bin/caddy
COPY --from=build /src/go.mod /src/go.sum /modules.txt /module.json /usr/share/caddy-build/
COPY deploy/caddy/go.mod /tmp/reviewed-go.mod
COPY deploy/caddy/go.sum /tmp/reviewed-go.sum
RUN cmp /tmp/reviewed-go.mod /usr/share/caddy-build/go.mod \
    && cmp /tmp/reviewed-go.sum /usr/share/caddy-build/go.sum \
    && rm /tmp/reviewed-go.mod /tmp/reviewed-go.sum
WORKDIR /srv
EXPOSE 80 443
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
