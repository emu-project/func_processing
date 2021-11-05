FROM centos:centos6

RUN mkdir /ashs_bin /work_dir /atlas_dir /data_dir /app
COPY ashs-fastashs_beta /ashs_bin/ashs-fastashs_beta
COPY do_ashs.sh /app
ENV ASHS_ROOT=/ashs_bin/ashs-fastashs_beta

ENTRYPOINT [ "/app/do_ashs.sh" ]
CMD [ "-h" ]