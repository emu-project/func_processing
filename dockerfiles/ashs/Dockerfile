FROM ubuntu:16.04

ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --fix-missing \
    tcl

RUN mkdir /ashs_bin /work_dir /atlas_dir /data_dir /app
COPY ashs-fastashs_beta /ashs_bin/ashs-fastashs_beta
COPY do_ashs.sh /app
ENV ASHS_ROOT=/ashs_bin/ashs-fastashs_beta

ENTRYPOINT [ "/app/do_ashs.sh" ]
CMD [ "-h" ]