FROM --platform=linux/amd64 mambaorg/micromamba:1.0.0-bullseye-slim

COPY --chown=$MAMBA_USER:$MAMBA_USER docker/environment.yml /tmp/environment.yml
RUN micromamba install -y -n base -c conda-forge -f /tmp/environment.yml && \
        micromamba clean --all --yes

ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN --mount=type=bind,target=/natcap,source=. \
    cd /natcap && ls -la && python -m build --wheel --outdir=/tmp && pip install $(find /tmp/natcap.invest -name "*.whl") && rm /tmp/*.whl

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "python", "-m", "natcap.invest"]
